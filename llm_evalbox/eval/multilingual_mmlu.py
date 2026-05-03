# SPDX-License-Identifier: Apache-2.0
"""KMMLU / CMMLU / JMMLU — Korean / Chinese / Japanese MMLU.

Same shape as MMLU (subject-stratified, 4 choices), just localized prompts.
KMMLU stores `answer` as 0-3 int; CMMLU/JMMLU as a letter (A-D).
`normalize_answer` handles both.
"""

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


class _MultilingualMMLU(BaseBenchmark):
    """Shared base. Concrete subclasses set `name`, `_dataset_key`,
    `_test_filename`, `_instruction_template`. Set `_one_indexed = True` if
    the upstream answer field is 1-based instead of 0-based or letter-based."""

    quick_size = 200
    _dataset_key: str = ""
    _test_filename: str = ""
    _instruction_template: str = (
        "Multiple choice question on {subject}. Answer with just the letter."
    )
    _one_indexed: bool = False

    async def load_dataset(self, sample_size: int = 0) -> list[dict]:
        files = ensure_dataset(self._dataset_key)
        raw = load_jsonl(files[self._test_filename])
        items: list[dict] = []
        for r in raw:
            choices = list(r.get("choices") or [])
            if len(choices) < 2:
                continue
            ans_raw = r.get("answer")
            if self._one_indexed and isinstance(ans_raw, int):
                ans_raw = ans_raw - 1
            ans = normalize_answer(ans_raw, choices)
            if not ans:
                continue
            items.append({
                "id": str(len(items)),
                "question": r.get("question", ""),
                "choices": choices,
                "answer": ans,
                "subject": r.get("subject", "unknown"),
            })
        logger.info("%s: %d items loaded", self.name, len(items))
        return stratified_sample(items, sample_size, key="subject")

    def get_max_tokens(self) -> int:
        return 8

    def format_prompt(self, item: dict) -> list[Message]:
        subject = (item.get("subject") or "unknown").replace("_", " ").title()
        return format_mc_prompt(
            instruction=self._instruction_template.format(subject=subject),
            question=item["question"],
            choices=item["choices"],
        )

    def extract_answer(self, response: str, item: dict) -> str:
        return extract_letter(response, item)

    def check_answer(self, predicted: str, item: dict) -> bool:
        return check_letter(predicted, item)

    def get_category(self, item: dict) -> str | None:
        return item.get("subject")


class KMMLUBenchmark(_MultilingualMMLU):
    name = "kmmlu"
    _dataset_key = "kmmlu"
    _test_filename = "kmmlu_test.jsonl"
    _one_indexed = True  # KMMLU stores 1..4, not 0..3
    _instruction_template = (
        "다음은 {subject}에 관한 객관식 문제입니다. 정답 한 글자만 답하세요."
    )


class CMMLUBenchmark(_MultilingualMMLU):
    name = "cmmlu"
    _dataset_key = "cmmlu"
    _test_filename = "cmmlu_test.jsonl"
    _instruction_template = (
        "下面是关于{subject}的单项选择题。请只回答字母。"
    )


class JMMLUBenchmark(_MultilingualMMLU):
    name = "jmmlu"
    _dataset_key = "jmmlu"
    _test_filename = "jmmlu_test.jsonl"
    _instruction_template = (
        "{subject}に関する多肢選択問題です。アルファベット一文字で答えてください。"
    )
