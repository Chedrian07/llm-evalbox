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
_KNOWN_SAMPLING_KEYS: tuple[str, ...] = (
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
