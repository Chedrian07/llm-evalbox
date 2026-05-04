# SPDX-License-Identifier: Apache-2.0
"""Cache + config directory resolvers.

Layout (default, single user):

    ~/.cache/llm-evalbox/
        datasets/                  # populated by eval/datasets.ensure_dataset
        responses/                 # response cache (M2)
        runs/                      # legacy/explicit run dumps (M2 resume)
        runs.sqlite                # persistent history (cache/history.py)
    ~/.config/llm-evalbox/
        profiles.toml              # legacy CLI profiles (config/profile.py)
        learned_capabilities.json  # legacy doctor cache (adapters/learned.py)
        .env                       # user-global dotenv

Containerised: set `EVALBOX_DATA_DIR=/data`. Both the cache and config
trees move under that prefix (`/data/cache/...`, `/data/config/...`) so
a single host volume mount preserves all state across container
restarts. `EVALBOX_CACHE_DIR` keeps its old "force this exact path"
semantics — useful for tests or unusual layouts.

`evalbox-runs/` (per-CWD, per-run) is for human-facing run output and is
not under cache_root().
"""

from __future__ import annotations

import os
from pathlib import Path


def _data_root() -> Path | None:
    """Container-friendly base for both cache and config trees.

    Returns the resolved path when `EVALBOX_DATA_DIR` is set (non-empty),
    otherwise None so individual resolvers can fall back to their normal
    home-directory locations.
    """
    explicit = os.environ.get("EVALBOX_DATA_DIR")
    if not explicit or not explicit.strip():
        return None
    return Path(explicit).expanduser()


def cache_root() -> Path:
    """`EVALBOX_CACHE_DIR` > `$EVALBOX_DATA_DIR/cache` > `~/.cache/llm-evalbox`."""
    explicit = os.environ.get("EVALBOX_CACHE_DIR")
    if explicit:
        return Path(explicit).expanduser()
    data = _data_root()
    if data is not None:
        return data / "cache"
    return Path("~/.cache/llm-evalbox").expanduser()


def config_root() -> Path:
    """`EVALBOX_CONFIG_DIR` > `$EVALBOX_DATA_DIR/config` > `~/.config/llm-evalbox`."""
    explicit = os.environ.get("EVALBOX_CONFIG_DIR")
    if explicit:
        return Path(explicit).expanduser()
    data = _data_root()
    if data is not None:
        return data / "config"
    return Path("~/.config/llm-evalbox").expanduser()


def runs_dir() -> Path:
    return cache_root() / "runs"
