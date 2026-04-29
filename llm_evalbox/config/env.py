# SPDX-License-Identifier: Apache-2.0
"""Load .env files in priority order.

Order (later loads do NOT override earlier when override=False):
  1. cwd/.env                                (highest local priority)
  2. ~/.config/llm-evalbox/.env              (user-global)

A custom path provided via CLI is loaded first with override=True so it wins.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_env_files(explicit: str | None = None) -> list[Path]:
    """Apply .env values into os.environ. Returns the list of loaded files."""
    loaded: list[Path] = []
    if explicit:
        p = Path(explicit).expanduser()
        if p.exists():
            load_dotenv(p, override=True)
            loaded.append(p)
        else:
            logger.warning("env file not found: %s", p)

    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        load_dotenv(cwd_env, override=False)
        loaded.append(cwd_env)

    user_env = Path("~/.config/llm-evalbox/.env").expanduser()
    if user_env.exists():
        load_dotenv(user_env, override=False)
        loaded.append(user_env)

    return loaded


def env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name, "")
    if not v:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def env_int(name: str, default: int | None = None) -> int | None:
    v = os.environ.get(name, "")
    if not v:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def env_float(name: str, default: float | None = None) -> float | None:
    v = os.environ.get(name, "")
    if not v:
        return default
    try:
        return float(v)
    except ValueError:
        return default


def env_str(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    return v if v else default
