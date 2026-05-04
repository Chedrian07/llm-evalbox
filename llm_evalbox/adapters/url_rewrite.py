# SPDX-License-Identifier: Apache-2.0
"""Rewrite container-local hostnames to `host.docker.internal`.

When the backend runs inside a Docker container but the user points it
at a local LLM endpoint (vLLM / SGLang / Ollama on `localhost:8000`),
the container can't reach the host's loopback. Docker Desktop on
macOS/Windows + Linux with `--add-host=host.docker.internal:host-gateway`
expose the host as the special name `host.docker.internal`. This helper
rewrites a small set of loopback-equivalent hostnames to that name so
the user doesn't have to edit `.env` per environment.

The user's *input* `base_url` is preserved everywhere in the UI/state —
only the URL handed to `httpx.AsyncClient` (via `resolve_adapter`) is
rewritten. The result type carries `did_rewrite` so the SPA can show a
small notice.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger(__name__)

# Hosts that should be remapped to host.docker.internal when running
# inside a container. `0.0.0.0` is technically a "all-interfaces" bind
# but users often type it for vLLM and expect it to mean "localhost",
# so we treat it the same as 127.0.0.1.
HOST_REWRITES: tuple[str, ...] = ("localhost", "127.0.0.1", "::1", "0.0.0.0")
CONTAINER_HOST = "host.docker.internal"


def in_container() -> bool:
    """Return True when the process is running inside a container.

    Checked via:
      1. `EVALBOX_IN_DOCKER=1` (explicit, set by our Dockerfile).
      2. Existence of `/.dockerenv` (canonical for the docker runtime).
    """
    if os.environ.get("EVALBOX_IN_DOCKER") == "1":
        return True
    try:
        return Path("/.dockerenv").exists()
    except OSError:
        return False


def _resolve_mode(explicit: str | None) -> str:
    """auto | on | off — `auto` is "rewrite only inside a container"."""
    raw = (explicit if explicit is not None else os.environ.get("EVALBOX_LOCALHOST_REWRITE", ""))
    raw = (raw or "").strip().lower()
    if raw in ("on", "1", "true", "yes"):
        return "on"
    if raw in ("off", "0", "false", "no"):
        return "off"
    return "auto"


def rewrite_localhost(
    base_url: str,
    *,
    in_container_: bool | None = None,
    mode: str | None = None,
) -> tuple[str, bool]:
    """Return `(effective_url, did_rewrite)`.

    `mode`:
      - `auto` (default): rewrite only when `in_container()` is True.
      - `on`: always rewrite (useful when running outside Docker but
        forwarding to a sibling container via host-gateway).
      - `off`: never rewrite — global kill-switch.

    `in_container_`: pass explicitly for tests; defaults to live detection.

    Rewrite is host-only — port, scheme, path, and query are preserved.
    Non-loopback hosts (LAN IP, public DNS) and unparseable URLs pass
    through unchanged.
    """
    if not base_url:
        return base_url, False

    effective_mode = _resolve_mode(mode)
    if effective_mode == "off":
        return base_url, False

    if effective_mode == "auto":
        in_c = in_container() if in_container_ is None else in_container_
        if not in_c:
            return base_url, False

    try:
        parts = urlsplit(base_url)
    except ValueError:
        return base_url, False

    host = (parts.hostname or "").strip().lower()
    if host not in HOST_REWRITES:
        return base_url, False

    # Preserve port + userinfo in the netloc rebuild. urllib doesn't
    # round-trip these via .hostname, so we reconstruct manually.
    userinfo = ""
    if parts.username is not None:
        userinfo = parts.username
        if parts.password is not None:
            userinfo += f":{parts.password}"
        userinfo += "@"
    new_netloc = f"{userinfo}{CONTAINER_HOST}"
    if parts.port is not None:
        new_netloc += f":{parts.port}"

    rewritten = urlunsplit(
        (parts.scheme, new_netloc, parts.path, parts.query, parts.fragment)
    )
    logger.info("rewrote %s → %s", host, CONTAINER_HOST)
    return rewritten, True
