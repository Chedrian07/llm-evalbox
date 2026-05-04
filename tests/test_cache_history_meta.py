# SPDX-License-Identifier: Apache-2.0
"""History tags/notes/starred — schema migration + filtering."""

from __future__ import annotations

import pytest

from llm_evalbox.cache import list_runs, upsert_run
from llm_evalbox.cache.history import update_run_meta


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    # All history operations route through history_db_path() → cache_root()
    # → EVALBOX_DATA_DIR. Steering DATA_DIR to tmp gives every test a fresh
    # SQLite file (no `learned_capabilities.json` to worry about here).
    monkeypatch.setenv("EVALBOX_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("EVALBOX_CACHE_DIR", raising=False)
    monkeypatch.delenv("EVALBOX_CONFIG_DIR", raising=False)


def _seed(run_id: str, *, model: str = "m") -> None:
    upsert_run({
        "run_id": run_id,
        "started_at": "2026-05-04T00:00:00Z",
        "finished_at": "2026-05-04T00:01:00Z",
        "provider": {"model": model, "base_url": "https://x", "adapter": "auto"},
        "totals": {"accuracy_macro": 0.8, "cost_usd_estimated": 0.01},
        "benchmarks": [{"name": "mmlu"}],
    })


def test_new_columns_default_to_empty():
    _seed("r1")
    rows = list_runs()
    assert len(rows) == 1
    r = rows[0]
    assert r["tags"] == []
    assert r["notes"] is None
    assert r["starred"] is False


def test_update_starred_only():
    _seed("r1")
    assert update_run_meta("r1", starred=True) is True
    rows = list_runs()
    assert rows[0]["starred"] is True
    # tags/notes untouched
    assert rows[0]["tags"] == []
    assert rows[0]["notes"] is None


def test_update_partial_keeps_other_fields():
    _seed("r1")
    update_run_meta("r1", tags=["fast", "vision"])
    update_run_meta("r1", notes="initial gpt-5.4 sweep")
    rows = list_runs()
    assert rows[0]["tags"] == ["fast", "vision"]
    assert rows[0]["notes"] == "initial gpt-5.4 sweep"
    assert rows[0]["starred"] is False


def test_update_strips_commas_and_whitespace():
    _seed("r1")
    # Commas inside tag names would corrupt the comma-separated storage,
    # so they're stripped. Whitespace-only entries are dropped.
    update_run_meta("r1", tags=["good, model", "  ", "ok"])
    rows = list_runs()
    assert rows[0]["tags"] == ["good model", "ok"]


def test_update_returns_false_for_missing_run():
    assert update_run_meta("does-not-exist", starred=True) is False


def test_update_no_op_returns_false():
    _seed("r1")
    # All fields None → nothing to write.
    assert update_run_meta("r1", tags=None, notes=None, starred=None) is False


def test_filter_starred_only():
    _seed("r1")
    _seed("r2")
    update_run_meta("r2", starred=True)
    rows = list_runs(starred_only=True)
    assert {r["run_id"] for r in rows} == {"r2"}


def test_filter_by_tag_substring():
    _seed("r1")
    _seed("r2")
    _seed("r3")
    update_run_meta("r1", tags=["fast"])
    update_run_meta("r2", tags=["fast", "vision"])
    update_run_meta("r3", tags=["coding"])
    rows = list_runs(tag="fast")
    assert {r["run_id"] for r in rows} == {"r1", "r2"}


def test_clearing_tags_with_empty_list():
    _seed("r1")
    update_run_meta("r1", tags=["a", "b"])
    update_run_meta("r1", tags=[])
    rows = list_runs()
    assert rows[0]["tags"] == []


def test_repeated_alter_is_idempotent():
    # The fixture creates a fresh DB; the migration runs every connection.
    # If the second connection's ALTER were not idempotent we'd raise.
    _seed("r1")
    _seed("r2")
    update_run_meta("r1", starred=True)
    rows = list_runs()
    assert len(rows) == 2
