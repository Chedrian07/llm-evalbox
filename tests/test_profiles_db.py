# SPDX-License-Identifier: Apache-2.0
"""Profiles SQLite store — round trip + TOML import."""

from __future__ import annotations

import pytest

from llm_evalbox.cache import profiles_db
from llm_evalbox.config.profile import load_profile, profile_path


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("EVALBOX_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("EVALBOX_CACHE_DIR", raising=False)
    monkeypatch.delenv("EVALBOX_CONFIG_DIR", raising=False)


def test_save_and_load_round_trip():
    row = profiles_db.save_profile(
        "vllm-local",
        base_url="http://localhost:8000/v1",
        model="Qwen/Qwen3-32B",
        adapter="chat_completions",
        api_key_env="VLLM_KEY",
        extra_headers={"X-Foo": "bar"},
        sampling={"temperature": 0.6, "top_p": 0.95},
    )
    assert row["name"] == "vllm-local"
    assert row["base_url"] == "http://localhost:8000/v1"
    assert row["adapter"] == "chat_completions"
    assert row["extra_headers"] == {"X-Foo": "bar"}
    assert row["sampling"] == {"temperature": 0.6, "top_p": 0.95}

    fetched = profiles_db.load_profile_db("vllm-local")
    assert fetched == row


def test_save_replaces_fields_but_keeps_created_at():
    first = profiles_db.save_profile("p", base_url="http://a")
    updated = profiles_db.save_profile("p", base_url="http://b")
    assert updated["created_at"] == first["created_at"]
    assert updated["updated_at"] >= first["updated_at"]
    assert updated["base_url"] == "http://b"


def test_list_orders_by_recency():
    profiles_db.save_profile("a", base_url="http://a")
    profiles_db.save_profile("b", base_url="http://b")
    profiles_db.touch_last_used("a")
    rows = profiles_db.list_profiles()
    assert [r["name"] for r in rows] == ["a", "b"]


def test_delete_profile():
    profiles_db.save_profile("p", base_url="http://a")
    assert profiles_db.delete_profile("p") is True
    assert profiles_db.delete_profile("p") is False
    assert profiles_db.load_profile_db("p") is None


def test_empty_name_rejected():
    with pytest.raises(ValueError):
        profiles_db.save_profile("   ")


def test_toml_imported_once_then_skipped(tmp_path, monkeypatch):
    # Seed legacy TOML.
    p = profile_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        '[my-vllm]\n'
        'adapter = "chat_completions"\n'
        'base_url = "http://localhost:8000/v1"\n'
        'api_key_env = "VLLM_KEY"\n'
        '[my-vllm.sampling]\n'
        'temperature = 0.6\n'
    )

    # First list triggers import.
    rows = profiles_db.list_profiles()
    assert {r["name"] for r in rows} == {"my-vllm"}
    assert rows[0]["sampling"]["temperature"] == 0.6

    # Subsequent TOML edits do NOT bleed in.
    p.write_text(
        '[stale]\nbase_url = "http://stale"\n'
    )
    rows2 = profiles_db.list_profiles()
    assert {r["name"] for r in rows2} == {"my-vllm"}


def test_load_profile_via_config_module_uses_sqlite():
    profiles_db.save_profile(
        "openrouter",
        base_url="https://openrouter.ai/api/v1",
        model="anthropic/claude-3.5-sonnet",
        adapter="chat_completions",
        api_key_env="OPENROUTER_API_KEY",
    )
    p = load_profile("openrouter")
    assert p is not None
    assert p.adapter == "chat_completions"
    assert p.base_url == "https://openrouter.ai/api/v1"
    assert p.api_key_env == "OPENROUTER_API_KEY"


def test_touch_last_used_returns_none_for_missing():
    assert profiles_db.touch_last_used("nope") is None
