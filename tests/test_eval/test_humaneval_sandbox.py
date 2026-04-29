# SPDX-License-Identifier: Apache-2.0
"""Sandbox tier1 contract: passing solution → ok, infinite loop → timeout."""

from __future__ import annotations

import sys

import pytest

from llm_evalbox.eval._sandbox import (
    SandboxPolicy,
    accept_code_exec,
    run_python_with_check,
    run_python_with_stdin,
)


@pytest.fixture(autouse=True)
def _accept():
    accept_code_exec()


def test_sandbox_passing_solution():
    code = "def add(a, b):\n    return a + b\n"
    test = "def check(fn):\n    assert fn(2,3) == 5\n    assert fn(0,0) == 0\n"
    r = run_python_with_check(code, test, "add")
    assert r.passed is True
    assert r.error_kind == "ok"


def test_sandbox_failing_solution_runtime_error():
    code = "def add(a, b):\n    return a - b  # wrong\n"
    test = "def check(fn):\n    assert fn(2,3) == 5\n"
    r = run_python_with_check(code, test, "add")
    assert r.passed is False
    assert r.error_kind in ("runtime_error", "wrong_answer")  # AssertionError → runtime_error


def test_sandbox_compile_error():
    code = "def add(a, b):\n  return a +\n"  # syntax error
    test = "def check(fn):\n    pass\n"
    r = run_python_with_check(code, test, "add")
    assert r.passed is False
    assert r.error_kind == "compile_error"


@pytest.mark.skipif(sys.platform == "win32", reason="timeout test relies on POSIX")
def test_sandbox_timeout():
    code = "def loop():\n    while True: pass\n"
    test = "def check(fn): fn()\n"
    p = SandboxPolicy(timeout_s=2, cpu_s=3, memory_mb=256)
    r = run_python_with_check(code, test, "loop", policy=p)
    assert r.passed is False
    assert r.error_kind == "timeout"


def test_sandbox_stdin_stdout():
    code = "import sys\nprint(int(input()) * 2)\n"
    r = run_python_with_stdin(code, "21\n")
    assert r.passed is True
    assert "42" in r.stdout
