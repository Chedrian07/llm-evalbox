# SPDX-License-Identifier: Apache-2.0
"""GSM8K — 5-shot chain-of-thought grade-school math."""

from __future__ import annotations

import logging

from llm_evalbox.core.messages import Message
from llm_evalbox.eval.base import BaseBenchmark
from llm_evalbox.eval.datasets import deterministic_sample, ensure_dataset, load_jsonl
from llm_evalbox.eval.extract import (
    extract_numeric_answer,
    normalize_number,
)

logger = logging.getLogger(__name__)

FEW_SHOT = [
    ("There are 15 trees in the grove. Grove workers will plant trees in the grove "
     "today. After they are done, there will be 21 trees. How many trees did the grove "
     "workers plant today?",
     "There are 15 trees originally. Then there were 21 trees after some more were "
     "planted. So there must have been 21 - 15 = 6 trees planted. #### 6"),
    ("If there are 3 cars in the parking lot and 2 more cars arrive, how many cars are "
     "in the parking lot?",
     "There are originally 3 cars. Then 2 more arrive. So there are 3 + 2 = 5 cars. "
     "#### 5"),
    ("Leah had 32 chocolates and her sister had 42. If they ate 35, how many pieces do "
     "they have left in total?",
     "Originally, Leah had 32 chocolates and her sister had 42. So in total they had "
     "32 + 42 = 74. After eating 35, they had 74 - 35 = 39. #### 39"),
    ("Jason had 20 lollipops. He gave Denny some lollipops. Now Jason has 12 "
     "lollipops. How many lollipops did Jason give to Denny?",
     "Jason had 20 lollipops originally. Then he had 12 after giving some to Denny. "
     "So he gave Denny 20 - 12 = 8 lollipops. #### 8"),
    ("Shawn has five toys. For Christmas, he got two toys each from his mom and dad. "
     "How many toys does he have now?",
     "Shawn started with 5 toys. He got 2 from mom and 2 from dad, so 2 + 2 = 4 more "
     "toys. Now he has 5 + 4 = 9 toys. #### 9"),
]


class GSM8KBenchmark(BaseBenchmark):
    name = "gsm8k"
    quick_size = 200

    async def load_dataset(self, sample_size: int = 0) -> list[dict]:
        files = ensure_dataset("gsm8k")
        raw = load_jsonl(files["gsm8k_test.jsonl"])
        items: list[dict] = []
        for i, it in enumerate(raw):
            ans = extract_numeric_answer(it.get("answer", ""))
            items.append({
                "id": str(i),
                "question": it.get("question", ""),
                "answer": ans,
            })
        logger.info("GSM8K: %d items loaded", len(items))
        return deterministic_sample(items, sample_size)

    def get_max_tokens(self) -> int:
        return 512

    def format_prompt(self, item: dict) -> list[Message]:
        parts = [
            "Solve the following math problem step by step. "
            "End your answer with #### followed by the final numeric answer.\n",
        ]
        for q, a in FEW_SHOT:
            parts.append(f"Question: {q}")
            parts.append(f"Answer: {a}\n")
        parts.append(f"Question: {item['question']}")
        parts.append("Answer:")
        return [Message(role="user", content="\n".join(parts))]

    def extract_answer(self, response: str, item: dict) -> str:
        return extract_numeric_answer(response)

    def check_answer(self, predicted: str, item: dict) -> bool:
        if not predicted:
            return False
        return normalize_number(predicted) == normalize_number(item["answer"])
