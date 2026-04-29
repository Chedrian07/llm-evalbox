# SPDX-License-Identifier: Apache-2.0
"""Cache directory resolver.

Layout:

    ~/.cache/llm-evalbox/
        datasets/                  # populated by eval/datasets.ensure_dataset
        responses/                 # response cache (M2)
        runs/                      # legacy/explicit run dumps (M2 resume)

`evalbox-runs/` (per-CWD, per-run) is for human-facing run output and is
not under cache_root().
"""

from __future__ import annotations

import os
from pathlib import Path


def cache_root() -> Path:
    explicit = os.environ.get("EVALBOX_CACHE_DIR")
    if explicit:
        return Path(explicit).expanduser()
    return Path("~/.cache/llm-evalbox").expanduser()


def runs_dir() -> Path:
    return cache_root() / "runs"
