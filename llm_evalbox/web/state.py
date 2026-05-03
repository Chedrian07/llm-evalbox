# SPDX-License-Identifier: Apache-2.0
"""In-memory run registry (M1).

A run is started by POST /api/runs and produces a stream of SSE events under
GET /api/runs/{id}/events. Single-process; we do not persist across restarts
(persistent SQLite is M3).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def new_run_id() -> str:
    return f"evalbox-{_utc_now_iso().replace(':','-')}-{uuid.uuid4().hex[:8]}"


@dataclass
class RunState:
    run_id: str
    config: dict[str, Any]
    status: str = "queued"   # queued | running | completed | failed | cancelled
    started_at: str = field(default_factory=_utc_now_iso)
    finished_at: str | None = None
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    task: asyncio.Task | None = None
    final_payload: dict[str, Any] | None = None
    messages: list[dict[str, Any]] = field(default_factory=list)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)


class RunRegistry:
    """Single-process registry. Use a module-level singleton via `get_registry()`."""

    def __init__(self) -> None:
        self._runs: dict[str, RunState] = {}
        self._lock = asyncio.Lock()

    def create(self, config: dict[str, Any]) -> RunState:
        rid = new_run_id()
        state = RunState(run_id=rid, config=config)
        self._runs[rid] = state
        return state

    def get(self, run_id: str) -> RunState | None:
        return self._runs.get(run_id)

    def list(self) -> list[RunState]:
        return list(self._runs.values())

    async def cancel(self, run_id: str) -> bool:
        state = self._runs.get(run_id)
        if state is None:
            return False
        state.cancel_event.set()
        if state.task is not None and not state.task.done():
            state.task.cancel()
        state.status = "cancelled"
        state.finished_at = _utc_now_iso()
        return True


_REGISTRY: RunRegistry | None = None


def get_registry() -> RunRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = RunRegistry()
    return _REGISTRY
