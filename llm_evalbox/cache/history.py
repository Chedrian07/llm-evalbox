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
    payload         TEXT NOT NULL,
    tags            TEXT,
    notes           TEXT,
    starred         INTEGER NOT NULL DEFAULT 0
);
"""

# Idempotent column migrations for existing databases that predate the
# tags / notes / starred fields. Each ALTER TABLE is wrapped in a
# try/except because SQLite raises OperationalError when the column
# already exists. We do this every connection — overhead is negligible
# and it keeps multi-process upgrades correct (CLI + Web running side by
# side).
_MIGRATIONS: tuple[str, ...] = (
    "ALTER TABLE runs ADD COLUMN tags TEXT",
    "ALTER TABLE runs ADD COLUMN notes TEXT",
    "ALTER TABLE runs ADD COLUMN starred INTEGER NOT NULL DEFAULT 0",
)

_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at)",
    "CREATE INDEX IF NOT EXISTS idx_runs_model ON runs(model)",
    "CREATE INDEX IF NOT EXISTS idx_runs_starred ON runs(starred)",
)


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(history_db_path(), isolation_level=None)  # autocommit
    db.row_factory = sqlite3.Row
    try:
        db.executescript(_SCHEMA)
        for stmt in _MIGRATIONS:
            try:
                db.execute(stmt)
            except sqlite3.OperationalError:
                pass  # column already present
        for stmt in _INDEXES:
            db.execute(stmt)
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


_SELECT_COLS = (
    "run_id, started_at, finished_at, model, base_url, adapter, "
    "accuracy_macro, cost_usd, bench_count, tags, notes, starred"
)


def list_runs(
    *,
    limit: int = 100,
    model: str | None = None,
    starred_only: bool = False,
    tag: str | None = None,
) -> list[dict[str, Any]]:
    """Return summary rows newest first.

    `starred_only`: only rows with starred=1.
    `tag`: substring match against the comma-separated `tags` column.
    Tags are stored as a flat comma-joined string (we don't expect more
    than a handful per run); SQLite's `INSTR` is enough for filtering.
    """
    where: list[str] = []
    params: list[Any] = []
    if model:
        where.append("model = ?")
        params.append(model)
    if starred_only:
        where.append("starred = 1")
    if tag:
        where.append("(',' || COALESCE(tags, '') || ',') LIKE ?")
        params.append(f"%,{tag},%")
    sql = f"SELECT {_SELECT_COLS} FROM runs"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY started_at DESC LIMIT ?"
    params.append(limit)
    with _conn() as db:
        rows = db.execute(sql, tuple(params)).fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    out = dict(row)
    # Normalise tags from "a,b,c" → ["a","b","c"]; null → [] so the SPA
    # can iterate without a guard.
    raw = out.get("tags")
    out["tags"] = [t for t in (raw or "").split(",") if t]
    out["starred"] = bool(out.get("starred"))
    return out


def update_run_meta(
    run_id: str,
    *,
    tags: list[str] | None = None,
    notes: str | None = None,
    starred: bool | None = None,
) -> bool:
    """Partial update — only non-None fields are written.

    `tags`: full list replaces what's stored. Whitespace-only entries are
    dropped; commas inside tag names are stripped (they'd corrupt the
    `INSTR` filter).
    `notes`: empty string clears the field (caller intent).
    `starred`: True/False.
    """
    sets: list[str] = []
    params: list[Any] = []
    if tags is not None:
        cleaned = [t.strip().replace(",", "") for t in tags if t and t.strip()]
        sets.append("tags = ?")
        params.append(",".join(cleaned) if cleaned else None)
    if notes is not None:
        sets.append("notes = ?")
        params.append(notes if notes else None)
    if starred is not None:
        sets.append("starred = ?")
        params.append(1 if starred else 0)
    if not sets:
        return False
    params.append(run_id)
    with _conn() as db:
        cur = db.execute(
            f"UPDATE runs SET {', '.join(sets)} WHERE run_id = ?",
            tuple(params),
        )
    return cur.rowcount > 0


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
