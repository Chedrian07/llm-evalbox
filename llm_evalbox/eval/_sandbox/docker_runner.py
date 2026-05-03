# SPDX-License-Identifier: Apache-2.0
"""Tier 2 sandbox: docker run.

Used when `EVALBOX_SANDBOX=docker` (or the runner-selecting helper picks
this tier). Adds network=none + read-only fs + memory/cpu caps on top of
tier 1's RLIMIT, at the cost of a ~1s startup per item (mitigated by
larger `--sandbox-workers`).

We use the `python:3.11-slim` image by default. Override with
`EVALBOX_DOCKER_IMAGE`. The container reads the script from /code/script.py
mounted read-only, sends stdin / receives stdout via docker's stdio.

Falls back to tier 1 when docker is missing on the host or fails to start.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time

from llm_evalbox.eval._sandbox.policy import SandboxPolicy
from llm_evalbox.eval._sandbox.runner import SandboxResult, _classify

logger = logging.getLogger(__name__)


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        r = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True, text=True, timeout=4,
        )
        return r.returncode == 0
    except Exception:
        return False


def _image() -> str:
    return os.environ.get("EVALBOX_DOCKER_IMAGE", "python:3.11-slim")


def _run_in_docker(
    script: str, *, policy: SandboxPolicy, stdin: str | None = None
) -> SandboxResult:
    if not _docker_available():
        return SandboxResult(
            passed=False,
            error_kind="runtime_error",
            stderr="docker not available — falling back via runner.run_python_*",
        )

    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "script.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(script)

        cmd = [
            "docker", "run", "--rm",
            "--network=none",
            "--read-only",
            "--tmpfs", "/tmp:rw,size=64m",
            f"--memory={policy.memory_mb}m",
            "--memory-swap", f"{policy.memory_mb}m",   # disallow swap
            f"--cpus={1.0}",
            "--pids-limit", "128",
            "-v", f"{td}:/code:ro",
            "-w", "/code",
            "-i" if stdin is not None else "--init",
            _image(),
            "python", "/code/script.py",
        ]
        # Docker's --rm already cleans up; we still wrap it in a parent timeout.
        t0 = time.perf_counter()
        try:
            r = subprocess.run(
                cmd,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=policy.timeout_s + 5,  # leave docker startup overhead
            )
            elapsed = time.perf_counter() - t0
            kind = _classify(r.returncode, r.stderr or "", timed_out=False)
            # Docker reports OOM as exit 137 (SIGKILL); reclassify.
            if r.returncode == 137:
                kind = "memory"
            return SandboxResult(
                passed=(r.returncode == 0),
                error_kind=kind,
                stdout=r.stdout or "",
                stderr=(r.stderr or "")[:2000],
                returncode=r.returncode,
                elapsed_s=elapsed,
            )
        except subprocess.TimeoutExpired as e:
            elapsed = time.perf_counter() - t0
            return SandboxResult(
                passed=False,
                error_kind="timeout",
                stdout=(e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes | bytearray) else (e.stdout or ""))[:2000],
                stderr="docker timeout",
                returncode=-1,
                elapsed_s=elapsed,
            )


def run_python_with_check_docker(
    code: str, test_code: str, entry_point: str, *, policy: SandboxPolicy | None = None
) -> SandboxResult:
    p = policy or SandboxPolicy()
    script = f"{code}\n\n{test_code}\n\ncheck({entry_point})\n"
    return _run_in_docker(script, policy=p)


def run_python_with_stdin_docker(
    code: str, stdin: str, *, policy: SandboxPolicy | None = None
) -> SandboxResult:
    p = policy or SandboxPolicy()
    return _run_in_docker(code, policy=p, stdin=stdin)
