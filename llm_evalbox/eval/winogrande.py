# SPDX-License-Identifier: Apache-2.0
"""Winogrande — pronoun resolution, binary choice (option1 vs option2).

Each item has a sentence with `_` placeholder and two candidate fills.
We render the choices as a 2-option MC and use letter answers internally.
"""

from __future__ import annotations

import logging

from llm_evalbox.core.messages import Message
from llm_evalbox.eval._mc_common import check_letter, extract_letter
from llm_evalbox.eval.base import BaseBenchmark
from llm_evalbox.eval.datasets import (
    deterministic_sample,
    ensure_dataset,
    load_jsonl,
)

logger = logging.getLogger(__name__)


class WinograndeBenchmark(BaseBenchmark):
    name = "winogrande"
    quick_size = 200

    async def load_dataset(self, sample_size: int = 0) -> list[dict]:
        files = ensure_dataset("winogrande")
        raw = load_jsonl(files["winogrande_val.jsonl"])
        items: list[dict] = []
        for r in raw:
            o1 = r.get("option1", "")
            o2 = r.get("option2", "")
            if not o1 or not o2:
                continue
            ans_raw = str(r.get("answer", "")).strip()
            # Source uses 1-indexed: "1" → option1 → letter A, "2" → B
            if ans_raw == "1":
                letter = "A"
            elif ans_raw == "2":
                letter = "B"
            else:
                continue
            items.append({
                "id": str(r.get("id", len(items))),
                "sentence": r.get("sentence", ""),
                "choices": [o1, o2],
                "answer": letter,
            })
        logger.info("Winogrande: %d items loaded", len(items))
        return deterministic_sample(items, sample_size)

    def get_max_tokens(self) -> int:
        return 8

    def format_prompt(self, item: dict) -> list[Message]:
        body = (
            "Choose the option that best fills the blank in the sentence. "
            "Answer with just the letter (A or B).\n\n"
            f"Sentence: {item['sentence']}\n\n"
            f"A. {item['choices'][0]}\n"
            f"B. {item['choices'][1]}\n\n"
            "Answer:"
        )
        return [Message(role="user", content=body)]

    def extract_answer(self, response: str, item: dict) -> str:
        return extract_letter(response, item)

    def check_answer(self, predicted: str, item: dict) -> bool:
        return check_letter(predicted, item)
