# SPDX-License-Identifier: Apache-2.0
"""resolve_tier + tiered dispatcher with docker fallback."""

from __future__ import annotations

import pytest

from llm_evalbox.core.exceptions import SandboxError
from llm_evalbox.eval._sandbox import (
    accept_code_exec,
    resolve_tier,
    run_python_with_check_tiered,
    run_python_with_stdin_tiered,
)


@pytest.fixture(autouse=True)
def _accept():
    accept_code_exec()


def test_resolve_tier_default(monkeypatch):
    monkeypatch.delenv("EVALBOX_SANDBOX", raising=False)
    assert resolve_tier() == "subprocess"


def test_resolve_tier_explicit(monkeypatch):
    monkeypatch.delenv("EVALBOX_SANDBOX", raising=False)
    assert resolve_tier("docker") == "docker"
    assert resolve_tier("e2b") == "e2b"


def test_resolve_tier_env(monkeypatch):
    monkeypatch.setenv("EVALBOX_SANDBOX", "docker")
    assert resolve_tier() == "docker"


def test_resolve_tier_invalid():
    with pytest.raises(SandboxError):
        resolve_tier("frobnicate")


def test_tiered_check_works_in_subprocess_tier(monkeypatch):
    monkeypatch.setenv("EVALBOX_SANDBOX", "subprocess")
    code = "def add(a, b):\n    return a + b\n"
    test = "def check(fn):\n    assert fn(2,3) == 5\n"
    r = run_python_with_check_tiered(code, test, "add")
    assert r.passed is True


def test_tiered_stdin_works_in_subprocess_tier(monkeypatch):
    monkeypatch.setenv("EVALBOX_SANDBOX", "subprocess")
    code = "print(int(input()) * 2)\n"
    r = run_python_with_stdin_tiered(code, "21\n")
    assert r.passed is True
    assert "42" in r.stdout


def test_tiered_docker_falls_back_when_docker_missing(monkeypatch):
    """When EVALBOX_SANDBOX=docker but docker isn't on PATH, the dispatcher
    falls back to tier 1 transparently. Most CI machines won't have docker."""
    import shutil
    monkeypatch.setenv("EVALBOX_SANDBOX", "docker")
    if shutil.which("docker"):
        pytest.skip("docker is installed; this test only meaningful without it")
    code = "def add(a, b):\n    return a + b\n"
    test = "def check(fn):\n    assert fn(2,3) == 5\n"
    r = run_python_with_check_tiered(code, test, "add")
    assert r.passed is True   # tier1 fallback ran successfully
