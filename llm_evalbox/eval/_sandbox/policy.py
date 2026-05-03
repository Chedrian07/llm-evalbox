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


# Isolation matrix per tier (informational; tier1 also runs in this process's
# user, tier2 in a fresh container, tier3 in an external service).
ISOLATION = {
    "subprocess": {
        "network": "host (parent's connectivity)",
        "filesystem": "host (env whitelist; tempfile cleaned up)",
        "memory": "RLIMIT_AS / RLIMIT_DATA (partial on macOS)",
        "cpu": "RLIMIT_CPU + parent timeout",
    },
    "docker": {
        "network": "none (--network=none)",
        "filesystem": "read-only mount + 64M tmpfs at /tmp",
        "memory": "--memory + memory-swap == limit",
        "cpu": "--cpus=1 + parent timeout (timeout_s + 5)",
    },
    "e2b": {
        "network": "vendor-provided sandbox",
        "filesystem": "ephemeral",
        "memory": "vendor",
        "cpu": "vendor",
    },
}


def resolve_tier(explicit: str | None = None) -> str:
    """Pick a sandbox tier based on the explicit flag or `$EVALBOX_SANDBOX`."""
    val = (explicit or os.environ.get("EVALBOX_SANDBOX") or "subprocess").lower()
    if val not in ("subprocess", "docker", "e2b"):
        raise SandboxError(f"unknown sandbox tier {val!r}; expected subprocess|docker|e2b")
    return val


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
