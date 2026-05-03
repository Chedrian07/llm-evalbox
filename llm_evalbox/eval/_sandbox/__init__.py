# SPDX-License-Identifier: Apache-2.0
"""Sandbox tiers for code-execution benchmarks. M0 ships tier1 (subprocess)."""

from llm_evalbox.eval._sandbox.policy import (
    ISOLATION,
    SandboxPolicy,
    accept_code_exec,
    is_code_exec_accepted,
    require_accepted,
    resolve_tier,
)
from llm_evalbox.eval._sandbox.runner import (
    SandboxResult,
    run_python_with_check,
    run_python_with_stdin,
)


def run_python_with_check_tiered(
    code: str, test_code: str, entry_point: str,
    *, policy: SandboxPolicy | None = None, tier: str | None = None,
) -> SandboxResult:
    """Tier-aware dispatcher. tier defaults to `$EVALBOX_SANDBOX`."""
    eff = (tier or resolve_tier()).lower()
    if eff == "docker":
        from llm_evalbox.eval._sandbox.docker_runner import run_python_with_check_docker
        r = run_python_with_check_docker(code, test_code, entry_point, policy=policy)
        if r.error_kind == "runtime_error" and "docker not available" in (r.stderr or ""):
            return run_python_with_check(code, test_code, entry_point, policy=policy)
        return r
    if eff == "e2b":
        from llm_evalbox.eval._sandbox.e2b_runner import run_python_with_check_e2b
        r = run_python_with_check_e2b(code, test_code, entry_point, policy=policy)
        if r.error_kind == "runtime_error" and "e2b not available" in (r.stderr or ""):
            return run_python_with_check(code, test_code, entry_point, policy=policy)
        return r
    return run_python_with_check(code, test_code, entry_point, policy=policy)


def run_python_with_stdin_tiered(
    code: str, stdin: str,
    *, policy: SandboxPolicy | None = None, tier: str | None = None,
) -> SandboxResult:
    eff = (tier or resolve_tier()).lower()
    if eff == "docker":
        from llm_evalbox.eval._sandbox.docker_runner import run_python_with_stdin_docker
        r = run_python_with_stdin_docker(code, stdin, policy=policy)
        if r.error_kind == "runtime_error" and "docker not available" in (r.stderr or ""):
            return run_python_with_stdin(code, stdin, policy=policy)
        return r
    if eff == "e2b":
        from llm_evalbox.eval._sandbox.e2b_runner import run_python_with_stdin_e2b
        r = run_python_with_stdin_e2b(code, stdin, policy=policy)
        if r.error_kind == "runtime_error" and "e2b not available" in (r.stderr or ""):
            return run_python_with_stdin(code, stdin, policy=policy)
        return r
    return run_python_with_stdin(code, stdin, policy=policy)


__all__ = [
    "ISOLATION",
    "SandboxPolicy",
    "SandboxResult",
    "accept_code_exec",
    "is_code_exec_accepted",
    "require_accepted",
    "resolve_tier",
    "run_python_with_check",
    "run_python_with_check_tiered",
    "run_python_with_stdin",
    "run_python_with_stdin_tiered",
]
