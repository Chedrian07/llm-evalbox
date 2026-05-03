# SPDX-License-Identifier: Apache-2.0
"""Tier 3 sandbox: e2b (https://e2b.dev) — execute code on a hosted micro-VM.

This tier sends the script to e2b and pulls back stdout / stderr / exit
code. The host stays untouched. Cost is per-second of compute on the
user's e2b account.

Triggered by `EVALBOX_SANDBOX=e2b`. Requires:

  - `e2b_code_interpreter>=1` installed in the same env.
  - `E2B_API_KEY` exported.

When either is missing we return a `runtime_error` SandboxResult with a
short hint; the tiered dispatcher in `_sandbox/__init__.py` falls back to
tier 1 in that case so a misconfigured environment doesn't break a CI run.
"""

from __future__ import annotations

import logging
import os
import time

from llm_evalbox.eval._sandbox.policy import SandboxPolicy
from llm_evalbox.eval._sandbox.runner import SandboxResult, _classify

logger = logging.getLogger(__name__)


def _e2b_unavailable_reason() -> str | None:
    if os.environ.get("E2B_API_KEY") in (None, ""):
        return "E2B_API_KEY is unset"
    try:
        import e2b_code_interpreter  # noqa: F401
    except ImportError:
        return "e2b_code_interpreter package not installed (pip install e2b-code-interpreter)"
    return None


def _run_in_e2b(script: str, *, policy: SandboxPolicy, stdin: str | None = None) -> SandboxResult:
    reason = _e2b_unavailable_reason()
    if reason is not None:
        return SandboxResult(
            passed=False,
            error_kind="runtime_error",
            stderr=f"e2b not available — {reason}",
        )

    # Lazy-imported so missing extras never break Python loading.
    from e2b_code_interpreter import Sandbox  # type: ignore[import-not-found]

    t0 = time.perf_counter()
    try:
        with Sandbox.create(timeout=policy.timeout_s + 10) as sb:
            # The e2b SDK exposes a `notebook.exec_cell` that returns stdout/err.
            # If the script reads stdin, we materialize it via a temp file.
            if stdin is not None:
                # Write stdin to a file inside the sandbox, then redirect into the script.
                sb.files.write("/tmp/stdin.txt", stdin)
                script = "import sys; sys.stdin = open('/tmp/stdin.txt'); " + script
            r = sb.notebook.exec_cell(script, timeout=policy.timeout_s)
            elapsed = time.perf_counter() - t0
            stdout = "\n".join(getattr(r, "logs", {}).get("stdout", []) or [])
            stderr = "\n".join(getattr(r, "logs", {}).get("stderr", []) or [])
            err = getattr(r, "error", None)
            if err is not None:
                # e2b exposes errors as `Execution Error` objects with name/value.
                kind = _classify(1, str(err), timed_out=False)
                return SandboxResult(
                    passed=False, error_kind=kind,
                    stdout=stdout, stderr=(stderr or str(err))[:2000],
                    returncode=1, elapsed_s=elapsed,
                )
            return SandboxResult(
                passed=True, error_kind="ok",
                stdout=stdout, stderr=stderr[:2000],
                returncode=0, elapsed_s=elapsed,
            )
    except Exception as e:  # network failures, quota, etc.
        elapsed = time.perf_counter() - t0
        return SandboxResult(
            passed=False, error_kind="runtime_error",
            stderr=str(e)[:2000], elapsed_s=elapsed,
        )


def run_python_with_check_e2b(
    code: str, test_code: str, entry_point: str,
    *, policy: SandboxPolicy | None = None,
) -> SandboxResult:
    p = policy or SandboxPolicy()
    script = f"{code}\n\n{test_code}\n\ncheck({entry_point})\n"
    return _run_in_e2b(script, policy=p)


def run_python_with_stdin_e2b(
    code: str, stdin: str,
    *, policy: SandboxPolicy | None = None,
) -> SandboxResult:
    p = policy or SandboxPolicy()
    return _run_in_e2b(code, policy=p, stdin=stdin)
