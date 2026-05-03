# SPDX-License-Identifier: Apache-2.0
"""MMLU-Pro — extended MMLU with up to 10 choices and harder distractors."""

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
    ensure_dataset,
    load_jsonl,
    stratified_sample,
)

logger = logging.getLogger(__name__)


class MMLUProBenchmark(BaseBenchmark):
    name = "mmlu_pro"
    quick_size = 200

    async def load_dataset(self, sample_size: int = 0) -> list[dict]:
        files = ensure_dataset("mmlu_pro")
        raw = load_jsonl(files["mmlu_pro_test.jsonl"])
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
                "subject": r.get("subject", "unknown"),
            })
        logger.info("MMLU-Pro: %d items loaded", len(items))
        return stratified_sample(items, sample_size, key="subject")

    def get_max_tokens(self) -> int:
        return 8

    def format_prompt(self, item: dict) -> list[Message]:
        return format_mc_prompt(
            instruction=(
                f"The following is a multiple choice question about "
                f"{item['subject'].replace('_', ' ').title()}. "
                f"Answer with just the letter."
            ),
            question=item["question"],
            choices=item["choices"],
        )

    def extract_answer(self, response: str, item: dict) -> str:
        return extract_letter(response, item)

    def check_answer(self, predicted: str, item: dict) -> bool:
        return check_letter(predicted, item)

    def get_category(self, item: dict) -> str | None:
        return item.get("subject")
