# SPDX-License-Identifier: Apache-2.0
"""`cache_root()` / `config_root()` resolution under the various env knobs."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_evalbox.cache.store import cache_root, config_root


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    for n in ("EVALBOX_DATA_DIR", "EVALBOX_CACHE_DIR", "EVALBOX_CONFIG_DIR"):
        monkeypatch.delenv(n, raising=False)


def test_defaults_to_home_dirs():
    home = Path("~").expanduser()
    assert cache_root() == home / ".cache" / "llm-evalbox"
    assert config_root() == home / ".config" / "llm-evalbox"


def test_data_dir_overrides_both(monkeypatch, tmp_path):
    monkeypatch.setenv("EVALBOX_DATA_DIR", str(tmp_path))
    assert cache_root() == tmp_path / "cache"
    assert config_root() == tmp_path / "config"


def test_cache_dir_explicit_wins_over_data_dir(monkeypatch, tmp_path):
    explicit = tmp_path / "explicit-cache"
    monkeypatch.setenv("EVALBOX_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("EVALBOX_CACHE_DIR", str(explicit))
    assert cache_root() == explicit
    # config still picks up DATA_DIR — kill switch is per-tree.
    assert config_root() == tmp_path / "data" / "config"


def test_config_dir_explicit_wins_over_data_dir(monkeypatch, tmp_path):
    explicit = tmp_path / "explicit-config"
    monkeypatch.setenv("EVALBOX_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("EVALBOX_CONFIG_DIR", str(explicit))
    assert config_root() == explicit
    assert cache_root() == tmp_path / "data" / "cache"


def test_empty_data_dir_falls_back(monkeypatch):
    monkeypatch.setenv("EVALBOX_DATA_DIR", "   ")
    home = Path("~").expanduser()
    assert cache_root() == home / ".cache" / "llm-evalbox"
    assert config_root() == home / ".config" / "llm-evalbox"
