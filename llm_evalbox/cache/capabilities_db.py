# SPDX-License-Identifier: Apache-2.0
"""SQLite-backed learned capabilities store.

Lives in the same `runs.sqlite` as run history so a single host volume
mount (or one ALTER trip to delete) covers both. The schema is:

    learned_capabilities(
        model_pattern   TEXT PRIMARY KEY,  -- exact model name from the wire
        drop_params     TEXT NOT NULL,     -- JSON list of unsupported keys
        learned_at      TEXT NOT NULL,
        success_count   INTEGER NOT NULL DEFAULT 0,
        failure_count   INTEGER NOT NULL DEFAULT 0
    )

JSON migration:
- On first lookup we import the legacy `learned_capabilities.json` if it
  exists and we haven't already imported (sentinel row in `_meta`). The
  JSON file is left in place as a downgrade safety net — only one-way
  read.

Lookup semantics match the legacy JSON store: exact model name first,
then the longest substring match against any stored pattern. This keeps
`gpt-5.4-mini` learned with prefix `gpt-5.4` working.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_evalbox.cache.history import history_db_path

logger = logging.getLogger(__name__)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS learned_capabilities (
    model_pattern   TEXT PRIMARY KEY,
    drop_params     TEXT NOT NULL,
    learned_at      TEXT NOT NULL,
    success_count   INTEGER NOT NULL DEFAULT 0,
    failure_count   INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS _meta (
    key             TEXT PRIMARY KEY,
    value           TEXT
);
"""


def _now_iso() -> str:
    # Microsecond precision so back-to-back writes (within the same
    # second) sort stably by `learned_at`. Display surfaces in
    # `list_all` truncate via the SPA when needed.
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(history_db_path(), isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        db.executescript(_SCHEMA)
        yield db
    finally:
        db.close()


def _legacy_json_path() -> Path:
    # Imported lazily so test fixtures that monkeypatch
    # `adapters.learned.store_path` still take effect.
    from llm_evalbox.adapters.learned import store_path
    return store_path()


def _maybe_import_legacy_json() -> None:
    """One-shot import of the JSON file. Safe to call repeatedly."""
    sentinel = "caps_imported_at"
    with _conn() as db:
        cur = db.execute("SELECT value FROM _meta WHERE key = ?", (sentinel,))
        if cur.fetchone() is not None:
            return
        path = _legacy_json_path()
        imported = 0
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                models = (data or {}).get("models", {}) or {}
                for model, entry in models.items():
                    drop_params = entry.get("drop_params") or []
                    learned_at = entry.get("learned_at") or _now_iso()
                    db.execute(
                        """
                        INSERT INTO learned_capabilities(model_pattern, drop_params,
                                                        learned_at)
                        VALUES(?, ?, ?)
                        ON CONFLICT(model_pattern) DO NOTHING
                        """,
                        (model, json.dumps(sorted(drop_params)), learned_at),
                    )
                    imported += 1
            except Exception as e:  # pragma: no cover — disk read best-effort
                logger.warning("learned-caps JSON import failed: %s", e)
        db.execute(
            "INSERT OR REPLACE INTO _meta(key, value) VALUES(?, ?)",
            (sentinel, _now_iso()),
        )
        if imported:
            logger.info("imported %d learned-capability entries from JSON", imported)


def remember(model: str, drop_params: list[str]) -> None:
    """Upsert an entry. `drop_params` replaces what's stored — caller
    should pass the full set (e.g. union of old + newly learned)."""
    if not model:
        return
    _maybe_import_legacy_json()
    with _conn() as db:
        db.execute(
            """
            INSERT INTO learned_capabilities(model_pattern, drop_params, learned_at)
            VALUES(?, ?, ?)
            ON CONFLICT(model_pattern) DO UPDATE SET
                drop_params = excluded.drop_params,
                learned_at  = excluded.learned_at
            """,
            (model, json.dumps(sorted(set(drop_params))), _now_iso()),
        )


def lookup_exact(model: str) -> list[str]:
    """Exact-match lookup only. Used by `learned.remember()`'s monotone
    union — substring fallback at write-time would pollute longer
    patterns with their shorter prefix's params."""
    if not model:
        return []
    _maybe_import_legacy_json()
    with _conn() as db:
        row = db.execute(
            "SELECT drop_params FROM learned_capabilities WHERE model_pattern = ?",
            (model,),
        ).fetchone()
    return _parse_params(row["drop_params"]) if row is not None else []


def lookup(model: str) -> list[str]:
    """Return drop_params for `model`. Exact match first, then longest
    substring match (so `gpt-5.4` learned matches a runtime `gpt-5.4-mini`)."""
    if not model:
        return []
    exact = lookup_exact(model)
    if exact:
        return exact
    with _conn() as db:
        rows = db.execute(
            "SELECT model_pattern, drop_params FROM learned_capabilities"
        ).fetchall()
    candidates = [
        (r["model_pattern"], r["drop_params"])
        for r in rows
        if r["model_pattern"] in model
    ]
    if not candidates:
        return []
    candidates.sort(key=lambda x: -len(x[0]))
    return _parse_params(candidates[0][1])


def _parse_params(raw: str) -> list[str]:
    try:
        v = json.loads(raw)
        return list(v) if isinstance(v, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def bump_success(model: str) -> None:
    if not model:
        return
    with _conn() as db:
        db.execute(
            "UPDATE learned_capabilities SET success_count = success_count + 1 "
            "WHERE model_pattern = ?",
            (model,),
        )


def bump_failure(model: str) -> None:
    if not model:
        return
    with _conn() as db:
        db.execute(
            "UPDATE learned_capabilities SET failure_count = failure_count + 1 "
            "WHERE model_pattern = ?",
            (model,),
        )


def list_all() -> list[dict[str, Any]]:
    """Return every learned entry, newest-learned first."""
    _maybe_import_legacy_json()
    with _conn() as db:
        rows = db.execute(
            "SELECT model_pattern, drop_params, learned_at, success_count, failure_count "
            "FROM learned_capabilities ORDER BY learned_at DESC"
        ).fetchall()
    out = []
    for r in rows:
        out.append({
            "model": r["model_pattern"],
            "drop_params": _parse_params(r["drop_params"]),
            "learned_at": r["learned_at"],
            "success_count": r["success_count"],
            "failure_count": r["failure_count"],
        })
    return out


def forget(model: str) -> bool:
    if not model:
        return False
    with _conn() as db:
        cur = db.execute(
            "DELETE FROM learned_capabilities WHERE model_pattern = ?",
            (model,),
        )
    return cur.rowcount > 0


def clear() -> int:
    with _conn() as db:
        cur = db.execute("DELETE FROM learned_capabilities")
    return cur.rowcount
