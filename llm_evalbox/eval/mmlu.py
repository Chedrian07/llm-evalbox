# SPDX-License-Identifier: Apache-2.0
"""MMLU (Hendrycks et al. 2020) — 5-shot multiple choice across 57 subjects."""

from __future__ import annotations

import json
import logging
from typing import Any

from llm_evalbox.core.messages import Message
from llm_evalbox.eval.base import BaseBenchmark
from llm_evalbox.eval.datasets import (
    ensure_dataset,
    load_jsonl,
    stratified_sample,
)
from llm_evalbox.eval.extract import extract_mc_answer

logger = logging.getLogger(__name__)

ANSWER_MAP = {0: "A", 1: "B", 2: "C", 3: "D"}


def _readable_subject(s: str) -> str:
    return s.replace("_", " ").title()


def _parse_choices(field: Any) -> list[str]:
    if isinstance(field, list):
        return [str(c) for c in field]
    if isinstance(field, str):
        try:
            v = json.loads(field.replace("'", '"'))
            if isinstance(v, list):
                return [str(c) for c in v]
        except (json.JSONDecodeError, ValueError):
            pass
    return []


def _format_choices(question: str, choices: list[str]) -> str:
    parts = [question]
    for i, c in enumerate(choices):
        parts.append(f"{ANSWER_MAP[i]}. {c}")
    return "\n".join(parts)


class MMLUBenchmark(BaseBenchmark):
    name = "mmlu"
    quick_size = 200

    def __init__(self) -> None:
        self._few_shot: dict[str, list[dict]] = {}

    async def load_dataset(self, sample_size: int = 0) -> list[dict]:
        files = ensure_dataset("mmlu")
        test = load_jsonl(files["mmlu_test.jsonl"])
        dev = load_jsonl(files["mmlu_dev.jsonl"]) if "mmlu_dev.jsonl" in files else []

        items: list[dict] = []
        for raw in test:
            choices = _parse_choices(raw.get("choices", []))
            ans_idx = int(raw.get("answer", 0))
            items.append({
                "id": raw.get("id") or f"{raw.get('subject', 'x')}-{len(items)}",
                "question": raw.get("question", ""),
                "choices": choices,
                "answer": ANSWER_MAP.get(ans_idx, str(ans_idx)),
                "subject": raw.get("subject", "unknown"),
            })

        for raw in dev:
            sub = raw.get("subject", "unknown")
            choices = _parse_choices(raw.get("choices", []))
            ans_idx = int(raw.get("answer", 0))
            ex = {
                "question": raw.get("question", ""),
                "choices": choices,
                "answer": ANSWER_MAP.get(ans_idx, str(ans_idx)),
            }
            self._few_shot.setdefault(sub, [])
            if len(self._few_shot[sub]) < 5:
                self._few_shot[sub].append(ex)

        logger.info("MMLU: %d test items loaded", len(items))
        return stratified_sample(items, sample_size, key="subject")

    def get_max_tokens(self) -> int:
        return 8

    def format_prompt(self, item: dict) -> list[Message]:
        sub = item["subject"]
        parts = [
            f"The following are multiple choice questions about {_readable_subject(sub)}. "
            "Answer with just the letter (A, B, C, or D).\n",
        ]
        for ex in self._few_shot.get(sub, []):
            parts.append(_format_choices(ex["question"], ex["choices"]))
            parts.append(f"Answer: {ex['answer']}\n")
        parts.append(_format_choices(item["question"], item["choices"]))
        parts.append("Answer:")
        return [Message(role="user", content="\n".join(parts))]

    def extract_answer(self, response: str, item: dict) -> str:
        return extract_mc_answer(response, ["A", "B", "C", "D"])

    def check_answer(self, predicted: str, item: dict) -> bool:
        return predicted == item["answer"]

    def get_category(self, item: dict) -> str | None:
        return item.get("subject")
