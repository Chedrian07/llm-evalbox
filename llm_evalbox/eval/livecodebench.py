# SPDX-License-Identifier: Apache-2.0
"""LiveCodeBench — competitive programming, stdin → stdout judging.

Each problem has a list of public test cases; the model writes a script that
reads stdin and prints stdout. We run the first N tests (default 3) inside
the tier-1 sandbox and require all of them to match exactly (after stripping
trailing whitespace) for the answer to count as correct.

Cutoff filter (`--lcb-cutoff YYYY-MM-DD`) is plumbed through but only takes
effect on dataset entries that carry a `release_date` field. The bundled
JSONL does not currently include that field, so the filter is a no-op until
upstream data with timestamps is bundled.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from llm_evalbox.core.messages import Message
from llm_evalbox.eval._sandbox import (
    SandboxPolicy,
    require_accepted,
    run_python_with_stdin,
)
from llm_evalbox.eval.base import BaseBenchmark
from llm_evalbox.eval.datasets import deterministic_sample, ensure_dataset, load_jsonl
from llm_evalbox.eval.extract import extract_last_code_block

logger = logging.getLogger(__name__)

MAX_TESTS_PER_PROBLEM = 3
SANDBOX_POLICY = SandboxPolicy(timeout_s=30, cpu_s=35, memory_mb=256)


def _parse_test_cases(raw: Any) -> list[tuple[str, str]]:
    """Coerce `public_test_cases` (string or list) → [(stdin, expected_stdout), …]."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
    if not isinstance(raw, list):
        return []
    out: list[tuple[str, str]] = []
    for tc in raw:
        if not isinstance(tc, dict):
            continue
        stdin = tc.get("input", "")
        expected = tc.get("output", "")
        if not isinstance(stdin, str):
            stdin = str(stdin)
        if not isinstance(expected, str):
            expected = str(expected)
        out.append((stdin, expected))
    return out


class LiveCodeBenchBenchmark(BaseBenchmark):
    name = "livecodebench"
    quick_size = 100

    # Settable via CLI: BENCHMARKS[...]() → benchmark.cutoff = "2024-09-01"
    cutoff: str | None = None

    def is_code_bench(self) -> bool:
        return True

    async def load_dataset(self, sample_size: int = 0) -> list[dict]:
        require_accepted(self.name)
        files = ensure_dataset("livecodebench")
        raw = load_jsonl(files["livecodebench.jsonl"])
        items: list[dict] = []
        skipped_no_tests = 0
        skipped_cutoff = 0
        for i, r in enumerate(raw):
            tests = _parse_test_cases(r.get("public_test_cases", "[]"))
            if not tests:
                skipped_no_tests += 1
                continue
            release_date = r.get("release_date") or r.get("contest_date")
            if self.cutoff and isinstance(release_date, str) and release_date < self.cutoff:
                skipped_cutoff += 1
                continue
            items.append({
                "id": str(r.get("question_id", i)),
                "title": r.get("question_title", f"Problem {i}"),
                "description": r.get("question_content", ""),
                "tests": tests[:MAX_TESTS_PER_PROBLEM],
                "difficulty": r.get("difficulty", "") or "unknown",
                "starter_code": r.get("starter_code", "") or "",
                "answer": "(stdin/stdout)",
            })
        logger.info(
            "LiveCodeBench: %d problems loaded (skipped %d empty, %d below cutoff)",
            len(items), skipped_no_tests, skipped_cutoff,
        )
        return deterministic_sample(items, sample_size)

    def get_max_tokens(self) -> int:
        # Competitive problems often need more room for reasoning + code.
        return 8192

    def get_category(self, item: dict) -> str | None:
        return item.get("difficulty") or None

    def format_prompt(self, item: dict) -> list[Message]:
        starter = item.get("starter_code") or ""
        starter_block = f"\n\nStarter code:\n```python\n{starter}\n```\n" if starter.strip() else ""
        body = (
            "Solve the following programming problem in Python. "
            "Read input from stdin and print the output to stdout. "
            "Provide only the complete Python code in a single code block, "
            "no explanations before or after.\n\n"
            f"Problem:\n{item['description']}"
            f"{starter_block}\n\n"
            "Solution:"
        )
        return [Message(role="user", content=body)]

    def extract_answer(self, response: str, item: dict) -> str:
        return extract_last_code_block(response)

    def check_answer(self, predicted: str, item: dict) -> bool:
        if not predicted.strip():
            return False
        for stdin, expected in item["tests"]:
            r = run_python_with_stdin(predicted, stdin, policy=SANDBOX_POLICY)
            if not r.passed:
                return False
            if r.stdout.strip() != expected.strip():
                return False
        return True

    # Override scoring to surface sandbox error_kind into the result row.
    def _score_response(self, item, resp):
        try:
            predicted = self.extract_answer(resp.text, item)
        except Exception as e:
            logger.warning("extract_answer failed: %s", e)
            return False, "", "generation_failed"
        if not predicted.strip():
            return False, "", "generation_failed"

        # Run all tests, classify by the first failure mode.
        for stdin, expected in item["tests"]:
            r = run_python_with_stdin(predicted, stdin, policy=SANDBOX_POLICY)
            if not r.passed:
                kind = r.error_kind if r.error_kind != "ok" else "runtime_error"
                return False, predicted, kind
            if r.stdout.strip() != expected.strip():
                return False, predicted, "wrong_answer"
        return True, predicted, "ok"
