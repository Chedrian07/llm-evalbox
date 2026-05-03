# SPDX-License-Identifier: Apache-2.0
"""Persistent run-history store backed by SQLite at
`~/.cache/llm-evalbox/runs.sqlite`.

Schema is intentionally tiny — one row per run with the result.json blob
stored as TEXT. We deliberately avoid normalizing per-bench rows; the
result.json is the source of truth and queries that need bench-level data
should re-parse it. SQLite gets us cross-process listing (the CLI and the
web server can both read), atomic writes, and free indexing on `started_at`.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from llm_evalbox.cache.store import cache_root

logger = logging.getLogger(__name__)


def history_db_path() -> Path:
    p = cache_root() / "runs.sqlite"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    model           TEXT,
    base_url        TEXT,
    adapter         TEXT,
    accuracy_macro  REAL,
    cost_usd        REAL,
    bench_count     INTEGER,
    payload         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at);
CREATE INDEX IF NOT EXISTS idx_runs_model ON runs(model);
"""


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(history_db_path(), isolation_level=None)  # autocommit
    db.row_factory = sqlite3.Row
    try:
        db.executescript(_SCHEMA)
        yield db
    finally:
        db.close()


def upsert_run(payload: dict[str, Any]) -> None:
    """Insert or update a single run by `run_id`. Idempotent."""
    if "run_id" not in payload:
        return
    p = payload.get("provider", {}) or {}
    totals = payload.get("totals", {}) or {}
    blob = json.dumps(payload, ensure_ascii=False)
    try:
        with _conn() as db:
            db.execute(
                """
                INSERT INTO runs(run_id, started_at, finished_at, model, base_url,
                                 adapter, accuracy_macro, cost_usd, bench_count, payload)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    finished_at=excluded.finished_at,
                    accuracy_macro=excluded.accuracy_macro,
                    cost_usd=excluded.cost_usd,
                    bench_count=excluded.bench_count,
                    payload=excluded.payload
                """,
                (
                    payload["run_id"],
                    payload.get("started_at", ""),
                    payload.get("finished_at"),
                    p.get("model"),
                    p.get("base_url"),
                    p.get("adapter"),
                    totals.get("accuracy_macro"),
                    totals.get("cost_usd_estimated"),
                    len(payload.get("benchmarks", []) or []),
                    blob,
                ),
            )
    except sqlite3.Error as e:
        logger.warning("history: failed to persist run %s: %s", payload.get("run_id"), e)


def list_runs(*, limit: int = 100, model: str | None = None) -> list[dict[str, Any]]:
    """Return summary rows newest first."""
    with _conn() as db:
        if model:
            rows = db.execute(
                "SELECT run_id, started_at, finished_at, model, base_url, adapter, "
                "accuracy_macro, cost_usd, bench_count "
                "FROM runs WHERE model = ? ORDER BY started_at DESC LIMIT ?",
                (model, limit),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT run_id, started_at, finished_at, model, base_url, adapter, "
                "accuracy_macro, cost_usd, bench_count "
                "FROM runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def get_run(run_id: str) -> dict[str, Any] | None:
    with _conn() as db:
        row = db.execute("SELECT payload FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    try:
        return json.loads(row["payload"])
    except (json.JSONDecodeError, TypeError):
        return None


def delete_run(run_id: str) -> bool:
    with _conn() as db:
        cur = db.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
    return cur.rowcount > 0


def clear_runs() -> int:
    with _conn() as db:
        cur = db.execute("DELETE FROM runs")
    return cur.rowcount
