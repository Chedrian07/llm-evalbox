# SPDX-License-Identifier: Apache-2.0
"""Shared helpers for letter-labeled multiple-choice benchmarks.

Most academic MC benchmarks share the same shape:
  - a question (and optionally a context paragraph)
  - 2-10 choices
  - one correct letter (A, B, C, ...)
  - optional category for stratified scoring

We give each concrete benchmark a tiny `load_dataset` that produces the
common item shape, and reuse `format_prompt` / `extract_answer` /
`check_answer` from this module.
"""

from __future__ import annotations

from typing import Any

from llm_evalbox.core.messages import Message
from llm_evalbox.eval.extract import extract_mc_answer

DEFAULT_LETTERS = "ABCDEFGHIJ"


def normalize_answer(raw: Any, choices: list[str]) -> str:
    """Convert a benchmark's `answer` field into a single letter.

    Accepts:
      - already a letter (``"B"``)
      - integer index (``2`` → ``"C"``)
      - numeric string (``"2"`` → ``"C"`` if 0-indexed) — kmmlu, winogrande style
      - integer-as-string with 1-indexed semantics (``"1"|"2"`` for winogrande)
        — caller should pre-shift if 1-indexed.
    """
    if isinstance(raw, str):
        s = raw.strip()
        if len(s) == 1 and s.upper() in DEFAULT_LETTERS:
            return s.upper()
        if s.isdigit():
            i = int(s)
            return DEFAULT_LETTERS[i] if 0 <= i < len(choices) else ""
        return ""
    if isinstance(raw, int):
        return DEFAULT_LETTERS[raw] if 0 <= raw < len(choices) else ""
    return ""


def format_mc_prompt(
    *,
    instruction: str,
    question: str,
    choices: list[str],
    context: str | None = None,
    answer_prompt: str = "Answer:",
) -> list[Message]:
    """Render a typical letter-labeled MC prompt."""
    parts: list[str] = [instruction]
    if context:
        parts.append(f"Context: {context}\n")
    parts.append(f"Question: {question}\n" if context else question)
    for i, c in enumerate(choices):
        parts.append(f"{DEFAULT_LETTERS[i]}. {c}")
    parts.append(f"\n{answer_prompt}")
    return [Message(role="user", content="\n".join(parts))]


def valid_letters_for(item: dict) -> list[str]:
    """Letters valid for this item's choices count."""
    return list(DEFAULT_LETTERS[: len(item.get("choices", []))])


def extract_letter(response: str, item: dict) -> str:
    return extract_mc_answer(response, valid_letters_for(item))


def check_letter(predicted: str, item: dict) -> bool:
    return predicted == item.get("answer", "")
