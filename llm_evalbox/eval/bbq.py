# SPDX-License-Identifier: Apache-2.0
"""BBQ — bias benchmark for QA. Context + question + 3 choices. Category = bias axis."""

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


class BBQBenchmark(BaseBenchmark):
    name = "bbq"
    quick_size = 200

    async def load_dataset(self, sample_size: int = 0) -> list[dict]:
        files = ensure_dataset("bbq")
        raw = load_jsonl(files["bbq_test.jsonl"])
        items: list[dict] = []
        for r in raw:
            choices = list(r.get("choices") or [])
            if not choices:
                continue
            ans = normalize_answer(r.get("answer"), choices)
            if not ans:
                continue
            items.append({
                "id": str(r.get("id") or len(items)),
                "context": r.get("context", ""),
                "question": r.get("question", ""),
                "choices": choices,
                "answer": ans,
                "category": r.get("category", "") or None,
            })
        logger.info("BBQ: %d items loaded", len(items))
        return deterministic_sample(items, sample_size)

    def get_max_tokens(self) -> int:
        return 8

    def format_prompt(self, item: dict) -> list[Message]:
        return format_mc_prompt(
            instruction=(
                "Read the context and answer the question by selecting the most "
                "appropriate option. Answer with just the letter."
            ),
            context=item["context"],
            question=item["question"],
            choices=item["choices"],
        )

    def extract_answer(self, response: str, item: dict) -> str:
        return extract_letter(response, item)

    def check_answer(self, predicted: str, item: dict) -> bool:
        return check_letter(predicted, item)

    def get_category(self, item: dict) -> str | None:
        return item.get("category")
