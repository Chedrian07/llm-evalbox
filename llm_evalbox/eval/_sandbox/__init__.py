# SPDX-License-Identifier: Apache-2.0
"""Sandbox tiers for code-execution benchmarks. M0 ships tier1 (subprocess)."""

from llm_evalbox.eval._sandbox.policy import (
    SandboxPolicy,
    accept_code_exec,
    is_code_exec_accepted,
    require_accepted,
)
from llm_evalbox.eval._sandbox.runner import (
    SandboxResult,
    run_python_with_check,
    run_python_with_stdin,
)

__all__ = [
    "SandboxPolicy",
    "SandboxResult",
    "accept_code_exec",
    "is_code_exec_accepted",
    "require_accepted",
    "run_python_with_check",
    "run_python_with_stdin",
]
