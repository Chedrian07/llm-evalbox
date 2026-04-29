# SPDX-License-Identifier: Apache-2.0
"""HellaSwag — 0-shot commonsense continuation, 4 choices."""

from __future__ import annotations

import logging

from llm_evalbox.core.messages import Message
from llm_evalbox.eval.base import BaseBenchmark
from llm_evalbox.eval.datasets import deterministic_sample, ensure_dataset, load_jsonl
from llm_evalbox.eval.extract import extract_mc_answer

logger = logging.getLogger(__name__)

ANSWER_MAP = {0: "A", 1: "B", 2: "C", 3: "D"}


class HellaSwagBenchmark(BaseBenchmark):
    name = "hellaswag"
    quick_size = 200

    async def load_dataset(self, sample_size: int = 0) -> list[dict]:
        files = ensure_dataset("hellaswag")
        raw = load_jsonl(files["hellaswag_val.jsonl"])
        items: list[dict] = []
        for r in raw:
            label = r.get("label", 0)
            try:
                ans_idx = int(label)
            except (TypeError, ValueError):
                ans_idx = 0
            items.append({
                "id": str(r.get("ind", len(items))),
                "context": r.get("ctx", ""),
                "endings": list(r.get("endings", []))[:4],
                "answer": ANSWER_MAP.get(ans_idx, "A"),
                "activity_label": r.get("activity_label", ""),
            })
        logger.info("HellaSwag: %d items loaded", len(items))
        return deterministic_sample(items, sample_size)

    def get_max_tokens(self) -> int:
        return 8

    def format_prompt(self, item: dict) -> list[Message]:
        parts = [
            "Choose the most plausible continuation. "
            "Answer with just the letter (A, B, C, or D).\n",
            f"Context: {item['context']}\n",
        ]
        for i, e in enumerate(item["endings"]):
            parts.append(f"{ANSWER_MAP[i]}. {e}")
        parts.append("\nAnswer:")
        return [Message(role="user", content="\n".join(parts))]

    def extract_answer(self, response: str, item: dict) -> str:
        return extract_mc_answer(response, ["A", "B", "C", "D"])

    def check_answer(self, predicted: str, item: dict) -> bool:
        return predicted == item["answer"]

    def get_category(self, item: dict) -> str | None:
        return item.get("activity_label") or None
