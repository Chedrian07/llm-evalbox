# SPDX-License-Identifier: Apache-2.0
"""Code-execution opt-in policy.

Code benchmarks refuse to run unless `--accept-code-exec` was passed or
`EVALBOX_ACCEPT_CODE_EXEC=1` is set. CLI also accepts an interactive prompt
which calls `accept_code_exec()` to flip the in-process flag.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from llm_evalbox.core.exceptions import SandboxError


@dataclass
class SandboxPolicy:
    tier: str = "subprocess"  # subprocess | docker | e2b
    timeout_s: int = 15
    memory_mb: int = 256
    cpu_s: int = 20
    workers: int = 4


_PROCESS_ACCEPT = False


def accept_code_exec() -> None:
    """Enable code execution for the rest of this process."""
    global _PROCESS_ACCEPT
    _PROCESS_ACCEPT = True


def is_code_exec_accepted() -> bool:
    if _PROCESS_ACCEPT:
        return True
    return os.environ.get("EVALBOX_ACCEPT_CODE_EXEC") == "1"


def require_accepted(bench_name: str) -> None:
    if not is_code_exec_accepted():
        raise SandboxError(
            f"benchmark {bench_name!r} executes model-generated code locally. "
            "Pass --accept-code-exec or set EVALBOX_ACCEPT_CODE_EXEC=1 to run."
        )
