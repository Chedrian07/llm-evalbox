# SPDX-License-Identifier: Apache-2.0
"""Thinking 3-mode handling: auto / on / off.

Three jobs:

1. `apply_thinking_to_request(req, mode)` — encode thinking on/off into the
   right request shape per provider family (chat_template_kwargs for vLLM/SGLang,
   reasoning.effort for Responses, extra for Anthropic via OpenRouter, etc.).
2. `parse_thinking(text, raw_response)` — split visible text from reasoning
   tokens (`<think>` blocks, `reasoning_content` field, Responses reasoning
   items).
3. `thinking_token_budget(...)` — clamp `max_tokens` when thinking is on.

Mapping matrix follows PLAN.md §6.2 / appendix B. Adapters call these
helpers; benchmarks never touch them directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

THINKING_MIN_TOKENS = 8192
THINKING_MAX_TOKENS = 32768

_THINK_TAG_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL)
_THINKING_TAG_RE = re.compile(r"<thinking>(.*?)</thinking>", re.DOTALL)


class ThinkingMode(str, Enum):
    AUTO = "auto"
    ON = "on"
    OFF = "off"


@dataclass(frozen=True)
class ThinkingFamily:
    """Pattern → encoding hints. Order matters in MATRIX (first match wins)."""

    pattern: re.Pattern[str]
    family: str
    # Tells `apply_thinking_to_request` which lever to flip:
    encoder: str  # "chat_template" | "reasoning_effort" | "openrouter_extra" | "gemini_extra" | "force_on"


MATRIX: list[ThinkingFamily] = [
    ThinkingFamily(re.compile(r"deepseek.*r1", re.I), "deepseek-r1", "force_on"),
    ThinkingFamily(re.compile(r"qwen.?3", re.I), "qwen3", "chat_template"),
    ThinkingFamily(re.compile(r"glm-?4\.[56]", re.I), "glm-4.5+", "chat_template"),
    ThinkingFamily(re.compile(r"^o[1-9]", re.I), "openai-o-series", "reasoning_effort"),
    ThinkingFamily(re.compile(r"gpt-5", re.I), "gpt-5", "reasoning_effort"),
    ThinkingFamily(re.compile(r"gpt-?oss", re.I), "gpt-oss", "reasoning_effort"),
    ThinkingFamily(re.compile(r"claude.*sonnet|claude.*opus|claude.*haiku", re.I),
                   "anthropic", "openrouter_extra"),
    ThinkingFamily(re.compile(r"gemini", re.I), "gemini", "gemini_extra"),
]


def detect_family(model: str) -> ThinkingFamily | None:
    for fam in MATRIX:
        if fam.pattern.search(model):
            return fam
    return None


def apply_thinking_to_request(
    *,
    model: str,
    mode: ThinkingMode | str,
    chat_template_kwargs: dict[str, Any],
    reasoning_effort: str | None,
    extra: dict[str, Any],
) -> tuple[dict[str, Any], str | None, dict[str, Any], list[str]]:
    """Mutate-by-copy the three knobs adapters use.

    Returns (chat_template_kwargs, reasoning_effort, extra, warnings).

    `mode` semantics:
      - "off": disable thinking where possible; warn for force_on families.
      - "on":  enable thinking on the right knob; bump only the request flag,
               not max_tokens (caller does that via `thinking_token_budget`).
      - "auto": no immediate change; the orchestrator decides after the first
               batch and re-runs with mode="on" if `<think>` was observed.
    """
    if isinstance(mode, str):
        mode = ThinkingMode(mode)

    ct = dict(chat_template_kwargs)
    ex = dict(extra)
    re_eff = reasoning_effort
    warnings: list[str] = []

    fam = detect_family(model)

    if mode == ThinkingMode.AUTO:
        return ct, re_eff, ex, warnings

    enabled = mode == ThinkingMode.ON

    if fam is None:
        # No known family — best effort: forward chat_template_kwargs.enable_thinking
        # so vLLM/SGLang routes that respect it pick it up.
        ct.setdefault("enable_thinking", enabled)
        return ct, re_eff, ex, warnings

    if fam.encoder == "chat_template":
        ct["enable_thinking"] = enabled
    elif fam.encoder == "reasoning_effort":
        # On → "high"; off → "low". OpenAI public o-series accepts "minimal"
        # but several gpt-5 variants (e.g. gpt-5.4-mini via cliproxy) reject it
        # and require one of {low, medium, high, xhigh}. "low" is the safe
        # cross-vendor floor.
        if re_eff is None:
            re_eff = "high" if enabled else "low"
    elif fam.encoder == "openrouter_extra":
        # Anthropic via OpenRouter chat-completions
        et = dict(ex.get("extended_thinking", {}))
        et["enabled"] = enabled
        if enabled and "budget_tokens" not in et:
            et["budget_tokens"] = 16384
        ex["extended_thinking"] = et
    elif fam.encoder == "gemini_extra":
        tc = dict(ex.get("thinking_config", {}))
        tc["thinking_budget"] = -1 if enabled else 0
        ex["thinking_config"] = tc
    elif fam.encoder == "force_on":
        # DeepSeek R1: thinking is intrinsic and not toggleable.
        if not enabled:
            warnings.append(
                f"thinking=off requested for {fam.family}, but the model has "
                "non-toggleable reasoning; ignoring."
            )
    return ct, re_eff, ex, warnings


def thinking_token_budget(*, base_max_tokens: int, model: str, thinking_on: bool) -> int:
    """Clamp `max_tokens` when thinking is on.

    - gpt-oss (Harmony) needs 4× because its analysis channel can consume the
      full budget before the final channel is emitted.
    - All other thinking-on families: clamp to [THINKING_MIN, THINKING_MAX].
    - thinking off: return base unchanged.
    """
    if not thinking_on:
        return base_max_tokens

    fam = detect_family(model)
    if fam is not None and fam.family == "gpt-oss":
        return max(base_max_tokens * 4, THINKING_MIN_TOKENS)

    return min(max(base_max_tokens, THINKING_MIN_TOKENS), THINKING_MAX_TOKENS)


def parse_thinking(text: str, raw_response: dict[str, Any] | None = None) -> tuple[str, str, bool]:
    """Split visible text from reasoning content.

    Returns `(visible_text, reasoning_text, observed)`.

    Order:
      1. `<think>...</think>` blocks (Qwen3, DeepSeek, gpt-oss in some routes).
      2. `<thinking>...</thinking>` blocks (Anthropic via OpenRouter).
      3. Provider-side reasoning fields in `raw_response`:
         - chat-completions: `choices[0].message.reasoning_content` (DeepSeek, Mistral).
         - Responses: `output[].type == "reasoning"` items.
    """
    reasoning_parts: list[str] = []
    observed = False

    visible = text or ""

    if "<think>" in visible:
        observed = True
        reasoning_parts.extend(m.group(1).strip() for m in _THINK_TAG_RE.finditer(visible))
        visible = _THINK_TAG_RE.sub("", visible).strip()

    if "<thinking>" in visible:
        observed = True
        reasoning_parts.extend(m.group(1).strip() for m in _THINKING_TAG_RE.finditer(visible))
        visible = _THINKING_TAG_RE.sub("", visible).strip()

    if raw_response:
        # Chat completions: reasoning_content on the message object
        choices = raw_response.get("choices") or []
        if choices:
            msg = (choices[0] or {}).get("message") or {}
            rc = msg.get("reasoning_content")
            if isinstance(rc, str) and rc.strip():
                observed = True
                reasoning_parts.append(rc.strip())

        # Responses API: output[].type == "reasoning"
        for item in raw_response.get("output", []) or []:
            if isinstance(item, dict) and item.get("type") == "reasoning":
                observed = True
                # Reasoning items can carry summary[].text or content[].text
                for sub_key in ("summary", "content"):
                    for sub in item.get(sub_key, []) or []:
                        if isinstance(sub, dict):
                            t = sub.get("text")
                            if isinstance(t, str) and t.strip():
                                reasoning_parts.append(t.strip())

    return visible.strip(), "\n\n".join(p for p in reasoning_parts if p), observed
