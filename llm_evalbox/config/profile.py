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

from llm_evalbox.core.exceptions import ConfigError

logger = logging.getLogger(__name__)

PROFILE_PATH = Path("~/.config/llm-evalbox/profiles.toml").expanduser()


@dataclass
class Profile:
    name: str
    adapter: str = "auto"
    base_url: str | None = None
    api_key_env: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    sampling: dict[str, float | int] = field(default_factory=dict)


def load_profile(name: str | None) -> Profile | None:
    """Return the named profile, or None when no profiles file exists."""
    if name is None:
        return None
    if not PROFILE_PATH.exists():
        raise ConfigError(
            f"profile {name!r} requested but {PROFILE_PATH} does not exist."
        )
    with open(PROFILE_PATH, "rb") as f:
        data = tomllib.load(f)
    if name not in data:
        raise ConfigError(f"profile {name!r} not found in {PROFILE_PATH}")
    raw = data[name]
    return Profile(
        name=name,
        adapter=str(raw.get("adapter", "auto")),
        base_url=raw.get("base_url"),
        api_key_env=raw.get("api_key_env"),
        extra_headers=dict(raw.get("extra_headers", {}) or {}),
        sampling=dict(raw.get("sampling", {}) or {}),
    )
