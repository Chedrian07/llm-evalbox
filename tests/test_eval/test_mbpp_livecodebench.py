# SPDX-License-Identifier: Apache-2.0
"""MBPP + LiveCodeBench unit tests — sandbox round-trip on tiny fixtures."""

from __future__ import annotations

import pytest

from llm_evalbox.eval._sandbox import accept_code_exec
from llm_evalbox.eval.livecodebench import LiveCodeBenchBenchmark, _parse_test_cases
from llm_evalbox.eval.mbpp import MBPPBenchmark, _wrap_assertions_as_check


@pytest.fixture(autouse=True)
def _accept():
    accept_code_exec()


# ---------------------------------------------------------------- MBPP
def test_mbpp_check_passes_on_correct_solution():
    bench = MBPPBenchmark()
    item = {
        "id": "1",
        "prompt": "double a number",
        "test_list": ["assert dbl(2) == 4", "assert dbl(0) == 0", "assert dbl(-3) == -6"],
        "test_setup_code": "",
    }
    code = "def dbl(x):\n    return x * 2\n"
    assert bench.check_answer(code, item) is True


def test_mbpp_check_fails_on_wrong_solution():
    bench = MBPPBenchmark()
    item = {
        "id": "1",
        "prompt": "double",
        "test_list": ["assert dbl(2) == 4"],
        "test_setup_code": "",
    }
    code = "def dbl(x):\n    return x + 1\n"
    assert bench.check_answer(code, item) is False


def test_mbpp_setup_code_runs_first():
    bench = MBPPBenchmark()
    item = {
        "id": "2",
        "prompt": "use SETUP global",
        "test_list": ["assert get_setup() == 42"],
        "test_setup_code": "SETUP = 42",
    }
    code = "def get_setup():\n    return SETUP\n"
    assert bench.check_answer(code, item) is True


def test_mbpp_score_response_classifies_compile_error():
    bench = MBPPBenchmark()
    item = {
        "id": "3",
        "prompt": "x",
        "test_list": ["assert f() == 1"],
        "test_setup_code": "",
    }

    class _Resp:
        text = "```python\ndef f(\n    return 1\n```"
        reasoning_text = ""

    correct, _, kind = bench._score_response(item, _Resp())
    assert correct is False
    assert kind == "compile_error"


def test_wrap_assertions_indents_each():
    out = _wrap_assertions_as_check(["assert a == 1", "assert b == 2"])
    assert out.startswith("def check(_):\n")
    assert "    assert a == 1" in out
    assert "    assert b == 2" in out


# ---------------------------------------------------------- LiveCodeBench
def test_lcb_parse_test_cases_string():
    raw = '[{"input": "1\\n", "output": "2\\n"}]'
    tcs = _parse_test_cases(raw)
    assert tcs == [("1\n", "2\n")]


def test_lcb_parse_test_cases_list():
    raw = [{"input": "a", "output": "A"}, {"input": "b", "output": "B"}]
    tcs = _parse_test_cases(raw)
    assert tcs == [("a", "A"), ("b", "B")]


def test_lcb_parse_test_cases_invalid_json():
    assert _parse_test_cases("not json") == []
    assert _parse_test_cases(None) == []


def test_lcb_check_passes():
    bench = LiveCodeBenchBenchmark()
    item = {
        "id": "p1",
        "tests": [("3 4\n", "7\n")],
    }
    code = "a, b = map(int, input().split())\nprint(a + b)\n"
    assert bench.check_answer(code, item) is True


def test_lcb_check_fails_on_wrong_output():
    bench = LiveCodeBenchBenchmark()
    item = {
        "id": "p1",
        "tests": [("3 4\n", "7\n")],
    }
    code = "a, b = map(int, input().split())\nprint(a * b)\n"
    assert bench.check_answer(code, item) is False


def test_lcb_check_runs_all_tests():
    """All test cases must pass; first failure short-circuits."""
    bench = LiveCodeBenchBenchmark()
    item = {
        "id": "p1",
        "tests": [
            ("3\n", "9\n"),     # square pass
            ("5\n", "25\n"),    # square pass
            ("7\n", "0\n"),     # square FAIL — code returns 49
        ],
    }
    code = "n = int(input())\nprint(n*n)\n"
    assert bench.check_answer(code, item) is False


def test_lcb_score_classifies_runtime_error():
    bench = LiveCodeBenchBenchmark()
    item = {
        "id": "p1",
        "tests": [("3\n", "9\n")],
    }

    class _Resp:
        text = "```python\nraise RuntimeError('boom')\n```"
        reasoning_text = ""

    correct, _, kind = bench._score_response(item, _Resp())
    assert correct is False
    assert kind == "runtime_error"


def test_lcb_cutoff_filter_drops_old_items(monkeypatch):
    bench = LiveCodeBenchBenchmark()
    bench.cutoff = "2024-01-01"
    raw = [
        {"question_id": "old", "public_test_cases": '[{"input":"","output":""}]',
         "release_date": "2023-06-01"},
        {"question_id": "new", "public_test_cases": '[{"input":"","output":""}]',
         "release_date": "2024-06-01"},
        {"question_id": "no_date", "public_test_cases": '[{"input":"","output":""}]'},
    ]

    import llm_evalbox.eval.livecodebench as lcb_mod
    monkeypatch.setattr(lcb_mod, "ensure_dataset", lambda _: {"livecodebench.jsonl": "/tmp/x"})
    monkeypatch.setattr(lcb_mod, "load_jsonl", lambda _: raw)

    items = pytest.run = None  # placeholder to avoid linter complaints
    import asyncio
    items = asyncio.run(bench.load_dataset(0))
    ids = {it["id"] for it in items}
    assert "new" in ids
    assert "no_date" in ids       # missing date is kept (can't filter what we can't see)
    assert "old" not in ids
