# SPDX-License-Identifier: Apache-2.0
"""SQLite-backed learned capabilities — round trip + JSON migration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_evalbox.adapters import learned
from llm_evalbox.cache import capabilities_db


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("EVALBOX_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("EVALBOX_CACHE_DIR", raising=False)
    monkeypatch.delenv("EVALBOX_CONFIG_DIR", raising=False)


def test_remember_and_lookup_exact():
    learned.remember("gpt-5.4-mini", ["seed", "top_k"])
    assert sorted(learned.lookup("gpt-5.4-mini")) == ["seed", "top_k"]


def test_remember_is_monotone_union():
    learned.remember("m1", ["seed"])
    learned.remember("m1", ["top_k"])
    # Both keys persisted — not overwritten.
    assert sorted(learned.lookup("m1")) == ["seed", "top_k"]


def test_substring_fallback_uses_longest_match():
    learned.remember("gpt-5", ["a"])
    learned.remember("gpt-5.4", ["b"])
    # "gpt-5.4-mini" should match the longer pattern, not the shorter one.
    assert learned.lookup("gpt-5.4-mini") == ["b"]


def test_lookup_unknown_model_is_empty():
    assert learned.lookup("never-seen") == []


def test_forget_and_clear():
    learned.remember("m1", ["seed"])
    learned.remember("m2", ["top_k"])
    assert learned.forget("m1") is True
    assert learned.forget("m1") is False
    assert {r["model"] for r in learned.list_all()} == {"m2"}
    assert learned.clear() == 1
    assert learned.list_all() == []


def test_list_all_newest_first():
    learned.remember("m1", ["a"])
    learned.remember("m2", ["b"])
    rows = learned.list_all()
    # m2 was learned more recently, should sort first.
    assert [r["model"] for r in rows] == ["m2", "m1"]


def test_legacy_json_imported_once(tmp_path):
    """Existing learned_capabilities.json should be imported on first
    SQLite access. Subsequent runs must NOT re-import even if the file
    is updated (we don't want a stale JSON to overwrite SQLite values)."""
    json_path = learned.store_path()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps({
        "version": 1,
        "models": {
            "legacy-model": {
                "drop_params": ["temperature", "seed"],
                "learned_at": "2026-01-01T00:00:00Z",
            },
        },
    }))

    # First lookup triggers import.
    assert sorted(learned.lookup("legacy-model")) == ["seed", "temperature"]

    # Subsequent edits to JSON should NOT bleed into SQLite.
    json_path.write_text(json.dumps({
        "version": 1,
        "models": {"legacy-model": {"drop_params": ["should_not_import"]}},
    }))
    assert sorted(learned.lookup("legacy-model")) == ["seed", "temperature"]


def test_import_skipped_when_no_json():
    # No file → import sentinel still set; lookup returns empty.
    assert learned.lookup("anything") == []
    # Direct DB call to confirm sentinel exists.
    rows = capabilities_db.list_all()
    assert rows == []


def test_bump_counters():
    learned.remember("m1", ["seed"])
    capabilities_db.bump_success("m1")
    capabilities_db.bump_success("m1")
    capabilities_db.bump_failure("m1")
    rows = capabilities_db.list_all()
    [row] = [r for r in rows if r["model"] == "m1"]
    assert row["success_count"] == 2
    assert row["failure_count"] == 1


def test_legacy_json_path_is_under_data_dir(tmp_path):
    # store_path() resolves through config_root() which respects EVALBOX_DATA_DIR.
    assert learned.store_path() == Path(tmp_path) / "config" / "learned_capabilities.json"
