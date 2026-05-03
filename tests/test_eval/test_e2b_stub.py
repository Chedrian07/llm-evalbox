# SPDX-License-Identifier: Apache-2.0
"""e2b sandbox tier3 — without the SDK installed we should fail-safe back
to tier 1 via the tiered dispatcher."""

from __future__ import annotations

import pytest

from llm_evalbox.eval._sandbox import (
    accept_code_exec,
    run_python_with_check_tiered,
    run_python_with_stdin_tiered,
)
from llm_evalbox.eval._sandbox.e2b_runner import _e2b_unavailable_reason


@pytest.fixture(autouse=True)
def _accept():
    accept_code_exec()


def test_e2b_unavailable_when_no_key(monkeypatch):
    monkeypatch.delenv("E2B_API_KEY", raising=False)
    reason = _e2b_unavailable_reason()
    assert reason is not None
    assert "E2B_API_KEY" in reason


def test_tiered_e2b_falls_back_to_tier1(monkeypatch):
    """EVALBOX_SANDBOX=e2b should still produce a passing result on a trivial
    program when e2b isn't configured — the dispatcher silently falls back."""
    monkeypatch.delenv("E2B_API_KEY", raising=False)
    monkeypatch.setenv("EVALBOX_SANDBOX", "e2b")
    code = "def add(a, b):\n    return a + b\n"
    test = "def check(fn):\n    assert fn(2,3) == 5\n"
    r = run_python_with_check_tiered(code, test, "add")
    assert r.passed is True


def test_tiered_e2b_stdin_falls_back(monkeypatch):
    monkeypatch.delenv("E2B_API_KEY", raising=False)
    monkeypatch.setenv("EVALBOX_SANDBOX", "e2b")
    code = "print(int(input()) * 2)\n"
    r = run_python_with_stdin_tiered(code, "21\n")
    assert r.passed is True
    assert "42" in r.stdout
