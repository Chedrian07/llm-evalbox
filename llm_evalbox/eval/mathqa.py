# SPDX-License-Identifier: Apache-2.0
"""MathQA — math word problems with letter-labeled multiple choice."""

from __future__ import annotations

import logging

from llm_evalbox.core.messages import Message
from llm_evalbox.eval._mc_common import (
    check_letter,
    extract_letter,
    format_mc_prompt,
    normalize_answer,
)
from llm_evalbox.eval.base import BaseBenchmark
from llm_evalbox.eval.datasets import (
    deterministic_sample,
    ensure_dataset,
    load_jsonl,
)

logger = logging.getLogger(__name__)


class MathQABenchmark(BaseBenchmark):
    name = "mathqa"
    quick_size = 200

    async def load_dataset(self, sample_size: int = 0) -> list[dict]:
        files = ensure_dataset("mathqa")
        raw = load_jsonl(files["mathqa_test.jsonl"])
        items: list[dict] = []
        for r in raw:
            choices = list(r.get("choices") or [])
            if not choices:
                continue
            items.append({
                "id": str(r.get("id") or len(items)),
                "question": r.get("question", ""),
                "choices": choices,
                "answer": normalize_answer(r.get("answer"), choices),
                "category": r.get("category", "") or None,
            })
        logger.info("MathQA: %d items loaded", len(items))
        return deterministic_sample(items, sample_size)

    def get_max_tokens(self) -> int:
        return 256  # CoT-friendly — model may show working

    def format_prompt(self, item: dict) -> list[Message]:
        return format_mc_prompt(
            instruction=(
                "Solve the following math problem and select the correct answer. "
                "Show brief reasoning, then answer with just the letter."
            ),
            question=item["question"],
            choices=item["choices"],
        )

    def extract_answer(self, response: str, item: dict) -> str:
        return extract_letter(response, item)

    def check_answer(self, predicted: str, item: dict) -> bool:
        return check_letter(predicted, item)

    def get_category(self, item: dict) -> str | None:
        return item.get("category")
