# SPDX-License-Identifier: Apache-2.0
"""Persistent store of doctor-learned drop_params per model.

Storage layout (current — SQLite-backed):

    `runs.sqlite` → `learned_capabilities` table
    (see `llm_evalbox/cache/capabilities_db.py`).

Backward compat:

    Legacy JSON file at `~/.config/llm-evalbox/learned_capabilities.json`
    is imported once on first SQLite access (sentinel row). The file is
    *not* deleted, so a downgrade can keep using it. We continue to
    expose `store_path()` for tests and the CLI's "where is it?" message.

Match rule: exact `model` key wins; failing that, the longest stored
pattern that is a substring of the runtime model wins (so a learned
`gpt-5.4` covers `gpt-5.4-mini` and `gpt-5.4-mini-2026-01-01`).
"""

from __future__ import annotations

import logging
from pathlib import Path

from llm_evalbox.cache import capabilities_db as _db
from llm_evalbox.cache.store import config_root

logger = logging.getLogger(__name__)


def store_path() -> Path:
    """Path to the legacy JSON file. Exposed mainly for the CLI's
    user-facing "look here" messages and for tests that want to seed
    pre-migration state."""
    return config_root() / "learned_capabilities.json"


def remember(model: str, drop_params: list[str]) -> None:
    """Upsert a learned entry. Monotone — we union with whatever is
    already stored on this exact pattern so capabilities never
    un-restrict by accident. We deliberately use exact lookup (not the
    substring-fallback `lookup`) to avoid polluting long-pattern entries
    with their shorter prefix's params."""
    if not model or not drop_params:
        return
    existing = set(_db.lookup_exact(model))
    _db.remember(model, sorted(existing.union(drop_params)))


def lookup(model: str) -> list[str]:
    return _db.lookup(model)


def list_all():
    return _db.list_all()


def forget(model: str) -> bool:
    return _db.forget(model)


def clear() -> int:
    return _db.clear()
