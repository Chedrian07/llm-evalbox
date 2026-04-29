# SPDX-License-Identifier: Apache-2.0
"""HumanEval — Python function completion. Verified by subprocess sandbox.

Code execution is opt-in: `--accept-code-exec` or EVALBOX_ACCEPT_CODE_EXEC=1.
The model output and the prompt's import block are combined to avoid
NameError on common library uses (re, math, typing.List, etc.).
"""

from __future__ import annotations

import logging
import re

from llm_evalbox.core.messages import Message
from llm_evalbox.eval._sandbox import (
    SandboxPolicy,
    require_accepted,
    run_python_with_check,
)
from llm_evalbox.eval.base import BaseBenchmark
from llm_evalbox.eval.datasets import deterministic_sample, ensure_dataset, load_jsonl
from llm_evalbox.eval.extract import extract_imports, extract_last_code_block

logger = logging.getLogger(__name__)


def _has_imports(code: str) -> bool:
    return any(
        line.strip().startswith(("import ", "from "))
        for line in code.split("\n")
    )


def _combine_with_prompt(extracted: str, prompt: str) -> str:
    """Compose a runnable function body from extracted code + prompt."""
    extracted = extracted.strip()
    imports = extract_imports(prompt)
    if "def " in extracted:
        if imports and not _has_imports(extracted):
            return imports + "\n\n" + extracted
        return extracted
    if extracted.startswith(("from ", "import ")):
        return extracted
    return prompt + extracted


_FUNCTION_DEF_RE = re.compile(r"^\s*def\s+\w+\s*\(", re.MULTILINE)


class HumanEvalBenchmark(BaseBenchmark):
    name = "humaneval"
    quick_size = 164  # full set is 164; <200, so always full

    def is_code_bench(self) -> bool:
        return True

    async def load_dataset(self, sample_size: int = 0) -> list[dict]:
        require_accepted(self.name)
        files = ensure_dataset("humaneval")
        raw = load_jsonl(files["humaneval.jsonl"])
        items: list[dict] = []
        for r in raw:
            items.append({
                "id": r["task_id"],
                "prompt": r["prompt"],
                "test": r["test"],
                "entry_point": r["entry_point"],
                "answer": "(unit tests)",
            })
        logger.info("HumanEval: %d problems loaded", len(items))
        return deterministic_sample(items, sample_size)

    def get_max_tokens(self) -> int:
        return 2048

    def format_prompt(self, item: dict) -> list[Message]:
        body = (
            "Complete the following Python function. "
            "Provide only the complete function implementation, no explanations.\n\n"
            f"{item['prompt']}"
        )
        return [Message(role="user", content=body)]

    def extract_answer(self, response: str, item: dict) -> str:
        block = extract_last_code_block(response)
        return _combine_with_prompt(block, item["prompt"])

    def check_answer(self, predicted: str, item: dict) -> bool:
        # Default scoring path is overridden by `_score_response` to capture
        # sandbox error_kind. This method exists to satisfy the ABC and gives
        # a useful return for tests that pass code directly.
        if not predicted.strip() or not _FUNCTION_DEF_RE.search(predicted):
            return False
        result = run_python_with_check(predicted, item["test"], item["entry_point"])
        return result.passed

    # Override scoring so error_kind reflects sandbox classification.
    def _score_response(self, item, resp):
        try:
            predicted = self.extract_answer(resp.text, item)
        except Exception as e:
            logger.warning("extract_answer failed: %s", e)
            return False, "", "generation_failed"

        if not predicted.strip() or not _FUNCTION_DEF_RE.search(predicted):
            return False, predicted, "generation_failed"

        result = run_python_with_check(
            predicted, item["test"], item["entry_point"],
            policy=SandboxPolicy(),
        )
        kind = result.error_kind
        if not result.passed and kind == "ok":
            kind = "wrong_answer"
        return result.passed, predicted, kind

    async def run(self, *args, **kwargs):
        # Run sandbox checks in a thread pool so they don't block the event loop.
        # Base.run already handles concurrency for the chat call; for HumanEval
        # we additionally route check_answer to a pool via _score_response,
        # which is sync. asyncio.to_thread isn't necessary because the work is
        # bounded and quick (<= timeout_s per item), but we expose a worker pool
        # for future tier upgrades.
        # NOTE: Base.run drives _score_response synchronously inside a single
        # await — sandbox calls happen serially per chat-batch. Acceptable for
        # M0 (164 items).
        return await super().run(*args, **kwargs)
