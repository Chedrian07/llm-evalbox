# SPDX-License-Identifier: Apache-2.0
"""Capability matrix — which sampling/prompting keys each model accepts.

Adapters call `capability_for(model)` then `strip_unsupported_keys()` to
delete keys the API will reject (or silently ignore). Pattern-based; the
first matching rule wins. Defaults are conservative (OpenAI public Chat
Completions baseline).

Doctor (M0) can later augment dynamically by parsing 4xx error text.
"""

from __future__ import annotations

import logging
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Capability:
    accepts_temperature: bool = True
    accepts_top_p: bool = True
    accepts_top_k: bool = False  # OpenAI public: false; vLLM/SGLang: true
    accepts_stop: bool = True
    accepts_seed: bool = True
    accepts_reasoning_effort: bool = False
    accepts_response_format: bool = True
    accepts_presence_penalty: bool = True
    accepts_frequency_penalty: bool = True
    accepts_repetition_penalty: bool = False  # vLLM-only key
    use_max_completion_tokens: bool = False  # o-series / gpt-5 require this name
    max_temperature_floor: float | None = None  # o-series: forces 1.0
    notes: str = ""


# Order matters — more specific patterns first.
CAPABILITY_RULES: list[tuple[re.Pattern[str], Capability]] = [
    (
        re.compile(r"^o[1-9]([\b\W]|$)", re.I),
        Capability(
            accepts_temperature=False,
            accepts_top_p=False,
            accepts_seed=False,
            accepts_presence_penalty=False,
            accepts_frequency_penalty=False,
            accepts_reasoning_effort=True,
            use_max_completion_tokens=True,
            max_temperature_floor=1.0,
            notes="OpenAI o-series: most sampling keys rejected; reasoning_effort respected.",
        ),
    ),
    (
        re.compile(r"gpt-5", re.I),
        Capability(
            accepts_reasoning_effort=True,
            use_max_completion_tokens=True,
            notes="GPT-5: reasoning_effort supported.",
        ),
    ),
    (
        re.compile(r"gpt-?oss", re.I),
        Capability(
            accepts_reasoning_effort=True,
            notes="gpt-oss (Harmony) — analysis channel; reasoning_effort respected.",
        ),
    ),
    (
        re.compile(r"deepseek.*r1", re.I),
        Capability(notes="DeepSeek-R1: thinking forced on, no toggle."),
    ),
    (
        re.compile(r"qwen.?3", re.I),
        Capability(
            accepts_top_k=True,
            accepts_repetition_penalty=True,
            notes="Qwen3 via vLLM/SGLang: chat_template_kwargs.enable_thinking respected.",
        ),
    ),
    (
        re.compile(r"glm-?4\.[56]", re.I),
        Capability(
            accepts_top_k=True,
            accepts_repetition_penalty=True,
            notes="GLM-4.5/4.6: chat_template_kwargs.enable_thinking respected.",
        ),
    ),
    (
        re.compile(r"claude", re.I),
        Capability(
            accepts_top_k=True,
            accepts_seed=False,
            notes="Anthropic via OpenRouter chat-completions.",
        ),
    ),
    (
        re.compile(r"gemini", re.I),
        Capability(
            accepts_seed=False,
            accepts_repetition_penalty=False,
            notes="Gemini OpenAI-compatible.",
        ),
    ),
    (
        re.compile(r"^(meta-llama|mistralai|google|qwen|alibaba)/.+|^llama|^mistral", re.I),
        Capability(
            accepts_top_k=True,
            accepts_repetition_penalty=True,
            notes="Open-weights via vLLM/SGLang/Ollama-style gateway: full sampling.",
        ),
    ),
]


def capability_for(model: str) -> Capability:
    """Return the first matching capability rule, or a default OpenAI-public profile."""
    for pat, cap in CAPABILITY_RULES:
        if pat.search(model):
            return cap
    return Capability()


# The full set of keys an adapter might place on the wire body.
KNOWN_SAMPLING_KEYS: tuple[str, ...] = (
    "temperature",
    "top_p",
    "top_k",
    "stop",
    "seed",
    "presence_penalty",
    "frequency_penalty",
    "repetition_penalty",
    "response_format",
    "reasoning_effort",
)
# Backward-compat alias (was private).
_KNOWN_SAMPLING_KEYS = KNOWN_SAMPLING_KEYS

# Patterns that match common 4xx "this parameter is unsupported" messages
# returned by various OpenAI-compatible gateways (OpenAI public, vLLM, SGLang,
# Together, Fireworks, OpenRouter, custom proxies). The captured group is the
# offending parameter name. We keep the patterns lenient — if a gateway uses a
# format we don't recognize, doctor's adaptation just stops; the user can fall
# back to --drop-params.
# `_Q` allows any combination of escaped/unescaped quotes around a token —
# many gateways embed messages inside JSON, so the quotes arrive escaped
# (e.g. `\"minimal\"`). Repeated to also handle the trailing quote.
_Q = r"[\\'\"`]*"

_UNSUPPORTED_PARAM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(rf"unrecognized\s+parameter[s]?:?\s*{_Q}(\w+){_Q}", re.I),
    # cliproxy / OpenAI Responses: 'Unsupported parameter: seed', also
    # 'Unsupported parameters: top_k'.
    re.compile(rf"unsupported\s+parameter[s]?:?\s*{_Q}(\w+){_Q}", re.I),
    re.compile(rf"{_Q}(\w+){_Q}\s+is\s+not\s+(?:supported|allowed|recognized)", re.I),
    re.compile(rf"unknown\s+(?:argument|key|parameter|field):\s*{_Q}(\w+){_Q}", re.I),
    re.compile(rf"invalid\s+value\s+for\s+{_Q}(\w+){_Q}", re.I),
    re.compile(rf"parameter\s+{_Q}(\w+){_Q}\s+(?:is\s+)?(?:not\s+supported|invalid|unknown)", re.I),
    # gpt-5.4-mini / cliproxy: 'level "minimal" not supported'
    # → reasoning_effort capability mismatch. We map the value name back to the
    # parameter when the offending value is a known reasoning_effort level.
    re.compile(rf"level\s+{_Q}(?P<val>none|minimal|low|medium|high|xhigh){_Q}\s+not\s+supported", re.I),
)

# Map values that show up in error messages back to the parameter name.
_VALUE_TO_PARAM = {
    "none": "reasoning_effort",
    "minimal": "reasoning_effort",
    "low": "reasoning_effort",
    "medium": "reasoning_effort",
    "high": "reasoning_effort",
    "xhigh": "reasoning_effort",
}


def parse_unsupported_param_error(message: str) -> set[str]:
    """Heuristic parse of a 4xx body to extract names of unsupported sampling keys.

    Returns a set of names that match `KNOWN_SAMPLING_KEYS`. Other tokens
    captured by the patterns are filtered out so we don't accidentally drop
    fields we control (model, messages, etc.).
    """
    found: set[str] = set()
    for rx in _UNSUPPORTED_PARAM_PATTERNS:
        for m in rx.finditer(message or ""):
            name = m.group("val") if "val" in m.groupdict() else m.group(1)
            # Map specific values back to their parameter (e.g. "minimal" → reasoning_effort)
            mapped = _VALUE_TO_PARAM.get(name.lower(), name)
            if mapped in KNOWN_SAMPLING_KEYS:
                found.add(mapped)
    return found


def _accept_for(cap: Capability, key: str) -> bool:
    accept = getattr(cap, f"accepts_{key}", None)
    if accept is None:
        return True  # unknown key: don't strip
    return bool(accept)


def strip_unsupported_keys(
    body: dict[str, Any],
    cap: Capability,
    user_drop: list[str] | None = None,
) -> dict[str, Any]:
    """Remove sampling keys the model rejects.

    - Capability says no → strip + DEBUG log.
    - User-supplied `drop_params` → strip + INFO log (forced).
    - `temperature` is clamped up to `max_temperature_floor` if set.
    - Returns a NEW dict; never mutates input.
    """
    out = deepcopy(body)
    for key in _KNOWN_SAMPLING_KEYS:
        if key in out and not _accept_for(cap, key):
            logger.debug("strip key %r (capability denied for this model)", key)
            out.pop(key, None)
    if user_drop:
        for key in user_drop:
            if key in out:
                logger.info("strip key %r (user-requested drop_params)", key)
                out.pop(key, None)

    if cap.max_temperature_floor is not None and "temperature" in out:
        floor = cap.max_temperature_floor
        if out["temperature"] != floor:
            logger.info(
                "clamp temperature %s → %s (model has fixed floor)",
                out["temperature"], floor,
            )
            out["temperature"] = floor

    return out
