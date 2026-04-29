# SPDX-License-Identifier: Apache-2.0
"""Tier 1 sandbox: subprocess + RLIMIT.

macOS Darwin partially ignores RLIMIT_AS, so we layer:
  - RLIMIT_AS / RLIMIT_DATA      (best-effort)
  - RLIMIT_CPU                   (hard CPU cap)
  - subprocess timeout           (wall clock)
  - environment whitelist        (no network / arbitrary creds inherited)

This is fine for CI HumanEval but should not be your last line of defense
against actively malicious code — that's tier2/3 (docker / e2b).
"""

from __future__ import annotations

import logging
import os
import resource
import subprocess
import sys
import tempfile
from dataclasses import dataclass

from llm_evalbox.eval._sandbox.policy import SandboxPolicy

logger = logging.getLogger(__name__)


@dataclass
class SandboxResult:
    passed: bool
    error_kind: str  # ok | timeout | memory | runtime_error | compile_error
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    elapsed_s: float = 0.0


def _make_preexec(policy: SandboxPolicy):
    mem_bytes = policy.memory_mb * 1024 * 1024
    cpu_s = policy.cpu_s

    def _set_limits():  # runs in child process before exec
        for rlim in (resource.RLIMIT_AS, resource.RLIMIT_DATA):
            try:
                resource.setrlimit(rlim, (mem_bytes, mem_bytes))
            except (ValueError, OSError):
                pass
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
        except (ValueError, OSError):
            pass
    return _set_limits


def _safe_env() -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/usr/local/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
    }


def _classify(returncode: int, stderr: str, timed_out: bool) -> str:
    if timed_out:
        return "timeout"
    if returncode == 0:
        return "ok"
    s = stderr.lower()
    if "memoryerror" in s or "out of memory" in s:
        return "memory"
    if "syntaxerror" in s or "indentationerror" in s:
        return "compile_error"
    return "runtime_error"


def _run(script: str, *, policy: SandboxPolicy, stdin: str | None = None) -> SandboxResult:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(script)
        tmp = f.name

    try:
        import time as _t

        kwargs = {
            "capture_output": True,
            "text": True,
            "timeout": policy.timeout_s,
            "env": _safe_env(),
        }
        if sys.platform != "win32":
            kwargs["preexec_fn"] = _make_preexec(policy)
        if stdin is not None:
            kwargs["input"] = stdin

        t0 = _t.perf_counter()
        try:
            r = subprocess.run([sys.executable, tmp], **kwargs)
            elapsed = _t.perf_counter() - t0
            kind = _classify(r.returncode, r.stderr or "", timed_out=False)
            return SandboxResult(
                passed=(r.returncode == 0),
                error_kind=kind,
                stdout=r.stdout or "",
                stderr=(r.stderr or "")[:2000],
                returncode=r.returncode,
                elapsed_s=elapsed,
            )
        except subprocess.TimeoutExpired as e:
            elapsed = _t.perf_counter() - t0
            return SandboxResult(
                passed=False,
                error_kind="timeout",
                stdout=(e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, (bytes, bytearray)) else (e.stdout or ""))[:2000],
                stderr="timeout",
                returncode=-1,
                elapsed_s=elapsed,
            )
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def run_python_with_check(
    code: str,
    test_code: str,
    entry_point: str,
    *,
    policy: SandboxPolicy | None = None,
) -> SandboxResult:
    """HumanEval-style: combine `code` + `test_code` + `check(entry_point)`."""
    p = policy or SandboxPolicy()
    script = f"{code}\n\n{test_code}\n\ncheck({entry_point})\n"
    return _run(script, policy=p)


def run_python_with_stdin(
    code: str,
    stdin: str,
    *,
    policy: SandboxPolicy | None = None,
) -> SandboxResult:
    """LiveCodeBench-style: feed stdin, capture stdout."""
    p = policy or SandboxPolicy()
    return _run(code, policy=p, stdin=stdin)
