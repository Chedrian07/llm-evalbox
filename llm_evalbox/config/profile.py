# SPDX-License-Identifier: Apache-2.0
"""TOML profile loader — `~/.config/llm-evalbox/profiles.toml`.

Profile shape:

    [my-vllm]
    adapter = "chat_completions"
    base_url = "http://localhost:8000/v1"
    api_key_env = "VLLM_KEY"
    extra_headers = { "X-Foo" = "bar" }

    [my-vllm.sampling]
    temperature = 0.6
    top_p = 0.95
    top_k = 20
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib  # type: ignore[unused-ignore]
else:  # pragma: no cover - 3.10 fallback
    import tomli as tomllib  # type: ignore[no-redef]

from llm_evalbox.cache.store import config_root
from llm_evalbox.core.exceptions import ConfigError

logger = logging.getLogger(__name__)


def profile_path() -> Path:
    return config_root() / "profiles.toml"


# Back-compat alias for callers/tests that imported the constant.
# Note: this resolves at import time — code that needs the live value
# (e.g. tests that monkeypatch EVALBOX_DATA_DIR) should call
# `profile_path()` instead.
PROFILE_PATH = profile_path()


@dataclass
class Profile:
    name: str
    adapter: str = "auto"
    base_url: str | None = None
    api_key_env: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    sampling: dict[str, float | int] = field(default_factory=dict)


def load_profile(name: str | None) -> Profile | None:
    """Return the named profile.

    Lookup order:
      1. SQLite store (`runs.sqlite` → profiles table) — written by the
         Web UI.
      2. TOML file at `~/.config/llm-evalbox/profiles.toml` — legacy /
         CLI users edit this directly.

    Returns None when `name` is None. Raises ConfigError when a name
    was requested but neither store has it (so the CLI can give a
    pointed error message instead of silently using defaults).
    """
    if name is None:
        return None

    # SQLite first — Web edits and the TOML one-shot import both land here.
    from llm_evalbox.cache import profiles_db
    row = profiles_db.load_profile_db(name)
    if row is not None:
        return Profile(
            name=row["name"],
            adapter=str(row.get("adapter") or "auto"),
            base_url=row.get("base_url"),
            api_key_env=row.get("api_key_env"),
            extra_headers=dict(row.get("extra_headers") or {}),
            sampling=dict(row.get("sampling") or {}),
        )

    # TOML fallback — only used when the SQLite store has no entry AND
    # the import-on-first-access has somehow been skipped (tests).
    path = profile_path()
    if not path.exists():
        raise ConfigError(
            f"profile {name!r} requested but {path} does not exist "
            f"(and no SQLite entry either)."
        )
    with open(path, "rb") as f:
        data = tomllib.load(f)
    if name not in data:
        raise ConfigError(f"profile {name!r} not found in {path}")
    raw = data[name]
    return Profile(
        name=name,
        adapter=str(raw.get("adapter", "auto")),
        base_url=raw.get("base_url"),
        api_key_env=raw.get("api_key_env"),
        extra_headers=dict(raw.get("extra_headers", {}) or {}),
        sampling=dict(raw.get("sampling", {}) or {}),
    )
