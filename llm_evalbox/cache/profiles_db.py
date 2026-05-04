# SPDX-License-Identifier: Apache-2.0
"""SQLite-backed connection profiles — Web UI editable.

Profiles let users save (base_url, model, adapter, api_key_env,
extra_headers, sampling) bundles under a name and switch between them
with one click. Pre-existing TOML profiles at
`~/.config/llm-evalbox/profiles.toml` are imported on first SQLite
access (one-shot, sentinel-guarded). The TOML file is left in place as
a downgrade safety net.

Schema:

    profiles(
        name            TEXT PRIMARY KEY,
        base_url        TEXT,
        model           TEXT,
        adapter         TEXT,
        api_key_env     TEXT,
        extra_headers   TEXT,    -- JSON
        sampling        TEXT,    -- JSON
        created_at      TEXT,
        updated_at      TEXT,
        last_used_at    TEXT
    )
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

from llm_evalbox.cache.history import history_db_path

logger = logging.getLogger(__name__)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    name            TEXT PRIMARY KEY,
    base_url        TEXT,
    model           TEXT,
    adapter         TEXT,
    api_key_env     TEXT,
    extra_headers   TEXT,
    sampling        TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    last_used_at    TEXT
);
CREATE TABLE IF NOT EXISTS _meta (
    key             TEXT PRIMARY KEY,
    value           TEXT
);
"""


def _now_iso() -> str:
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


def _legacy_toml_path() -> Path:
    # Resolved lazily so tests that flip EVALBOX_DATA_DIR mid-test
    # see fresh values.
    from llm_evalbox.config.profile import profile_path
    return profile_path()


def _maybe_import_legacy_toml() -> None:
    sentinel = "profiles_imported_at"
    with _conn() as db:
        cur = db.execute("SELECT value FROM _meta WHERE key = ?", (sentinel,))
        if cur.fetchone() is not None:
            return
        path = _legacy_toml_path()
        imported = 0
        if path.exists():
            try:
                with open(path, "rb") as f:
                    data = tomllib.load(f)
                ts = _now_iso()
                for name, raw in data.items():
                    if not isinstance(raw, dict):
                        continue
                    db.execute(
                        """
                        INSERT INTO profiles(name, base_url, model, adapter,
                                            api_key_env, extra_headers, sampling,
                                            created_at, updated_at)
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(name) DO NOTHING
                        """,
                        (
                            name,
                            raw.get("base_url"),
                            raw.get("model"),
                            raw.get("adapter") or "auto",
                            raw.get("api_key_env"),
                            json.dumps(dict(raw.get("extra_headers", {}) or {})),
                            json.dumps(dict(raw.get("sampling", {}) or {})),
                            ts,
                            ts,
                        ),
                    )
                    imported += 1
            except Exception as e:  # pragma: no cover
                logger.warning("profiles TOML import failed: %s", e)
        db.execute(
            "INSERT OR REPLACE INTO _meta(key, value) VALUES(?, ?)",
            (sentinel, _now_iso()),
        )
        if imported:
            logger.info("imported %d profiles from TOML", imported)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    extra_headers = _safe_json(row["extra_headers"]) or {}
    sampling = _safe_json(row["sampling"]) or {}
    return {
        "name": row["name"],
        "base_url": row["base_url"],
        "model": row["model"],
        "adapter": row["adapter"] or "auto",
        "api_key_env": row["api_key_env"],
        "extra_headers": extra_headers,
        "sampling": sampling,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_used_at": row["last_used_at"],
    }


def _safe_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def save_profile(
    name: str,
    *,
    base_url: str | None = None,
    model: str | None = None,
    adapter: str | None = None,
    api_key_env: str | None = None,
    extra_headers: dict[str, str] | None = None,
    sampling: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Insert or fully replace a profile. Used by the Web UI's
    "Save as profile…" form. Returns the stored row."""
    if not name or not name.strip():
        raise ValueError("profile name must be non-empty")
    name = name.strip()
    _maybe_import_legacy_toml()
    ts = _now_iso()
    with _conn() as db:
        existing = db.execute(
            "SELECT created_at FROM profiles WHERE name = ?", (name,)
        ).fetchone()
        created = existing["created_at"] if existing is not None else ts
        db.execute(
            """
            INSERT INTO profiles(name, base_url, model, adapter, api_key_env,
                                extra_headers, sampling, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                base_url = excluded.base_url,
                model = excluded.model,
                adapter = excluded.adapter,
                api_key_env = excluded.api_key_env,
                extra_headers = excluded.extra_headers,
                sampling = excluded.sampling,
                updated_at = excluded.updated_at
            """,
            (
                name,
                base_url,
                model,
                adapter or "auto",
                api_key_env,
                json.dumps(extra_headers or {}),
                json.dumps(sampling or {}),
                created,
                ts,
            ),
        )
    return load_profile_db(name)  # round-trip the canonical form


def load_profile_db(name: str) -> dict[str, Any] | None:
    if not name:
        return None
    _maybe_import_legacy_toml()
    with _conn() as db:
        row = db.execute(
            "SELECT * FROM profiles WHERE name = ?", (name,)
        ).fetchone()
    return _row_to_dict(row) if row is not None else None


def list_profiles() -> list[dict[str, Any]]:
    """Newest-first by `last_used_at` (NULLs last) then `updated_at`."""
    _maybe_import_legacy_toml()
    with _conn() as db:
        rows = db.execute(
            """
            SELECT * FROM profiles
            ORDER BY (last_used_at IS NULL), last_used_at DESC, updated_at DESC
            """
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def delete_profile(name: str) -> bool:
    if not name:
        return False
    with _conn() as db:
        cur = db.execute("DELETE FROM profiles WHERE name = ?", (name,))
    return cur.rowcount > 0


def touch_last_used(name: str) -> dict[str, Any] | None:
    """Bump last_used_at and return the refreshed row. Used by
    `POST /api/profiles/{name}/use` so the dropdown sorts by recency."""
    if not name:
        return None
    with _conn() as db:
        cur = db.execute(
            "UPDATE profiles SET last_used_at = ? WHERE name = ?",
            (_now_iso(), name),
        )
        if cur.rowcount == 0:
            return None
    return load_profile_db(name)
