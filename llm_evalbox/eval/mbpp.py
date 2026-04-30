# SPDX-License-Identifier: Apache-2.0
"""MBPP — Mostly Basic Python Problems.

Natural-language description → Python function. Verified by running the
`test_list` assertions inside the tier-1 sandbox. Same opt-in policy as
HumanEval (code execution requires `--accept-code-exec`).
"""

from __future__ import annotations

import logging

from llm_evalbox.core.messages import Message
from llm_evalbox.eval._sandbox import (
    SandboxPolicy,
    require_accepted,
    run_python_with_check,
)
from llm_evalbox.eval.base import BaseBenchmark
from llm_evalbox.eval.datasets import deterministic_sample, ensure_dataset, load_jsonl
from llm_evalbox.eval.extract import extract_last_code_block

logger = logging.getLogger(__name__)


def _wrap_assertions_as_check(test_list: list[str]) -> str:
    """Wrap an assertion list inside a `check(_unused)` function.

    `_sandbox.run_python_with_check` calls `check(entry_point)` on the executed
    script. MBPP doesn't expose an entry-point name, so we synthesize a no-arg
    check that runs the assertions; the entry-point parameter is ignored.
    """
    body = "\n".join("    " + ln for ln in test_list)
    return f"def check(_):\n{body}\n"


class MBPPBenchmark(BaseBenchmark):
    name = "mbpp"
    quick_size = 200

    def is_code_bench(self) -> bool:
        return True

    async def load_dataset(self, sample_size: int = 0) -> list[dict]:
        require_accepted(self.name)
        files = ensure_dataset("mbpp")
        raw = load_jsonl(files["mbpp.jsonl"])
        items: list[dict] = []
        for r in raw:
            test_list = r.get("test_list") or []
            if not test_list:
                continue
            items.append({
                "id": str(r["task_id"]),
                "prompt": r["prompt"],
                "test_list": list(test_list),
                "test_setup_code": r.get("test_setup_code", "") or "",
                "answer": "(test cases)",
            })
        logger.info("MBPP: %d problems loaded", len(items))
        return deterministic_sample(items, sample_size)

    def get_max_tokens(self) -> int:
        return 2048

    def format_prompt(self, item: dict) -> list[Message]:
        prompt = item["prompt"]
        # Show up to 3 sample tests so the model knows the function signature
        # and expected behavior. Keeps prompt size bounded.
        tests = item["test_list"][:3]
        body = (
            "Write a Python function to solve the following problem. "
            "Provide only the complete function implementation, no explanations.\n\n"
            f"Problem: {prompt}\n\n"
            "Test cases:\n"
            + "\n".join(tests)
            + "\n\nSolution:"
        )
        return [Message(role="user", content=body)]

    def extract_answer(self, response: str, item: dict) -> str:
        return extract_last_code_block(response)

    def check_answer(self, predicted: str, item: dict) -> bool:
        if not predicted.strip():
            return False
        setup = item.get("test_setup_code", "") or ""
        check_block = _wrap_assertions_as_check(item["test_list"])
        full_code = setup + ("\n\n" if setup else "") + predicted
        result = run_python_with_check(full_code, check_block, "None")
        return result.passed

    # Override scoring so error_kind reflects sandbox classification.
    def _score_response(self, item, resp):
        try:
            predicted = self.extract_answer(resp.text, item)
        except Exception as e:
            logger.warning("extract_answer failed: %s", e)
            return False, "", "generation_failed"
        if not predicted.strip():
            return False, "", "generation_failed"

        setup = item.get("test_setup_code", "") or ""
        check_block = _wrap_assertions_as_check(item["test_list"])
        full_code = setup + ("\n\n" if setup else "") + predicted
        result = run_python_with_check(
            full_code, check_block, "None",
            policy=SandboxPolicy(),
        )
        kind = result.error_kind
        if not result.passed and kind == "ok":
            kind = "wrong_answer"
        return result.passed, predicted, kind
