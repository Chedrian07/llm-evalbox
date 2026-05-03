# SPDX-License-Identifier: Apache-2.0
"""Response cache (PLAN.md §13.3).

Key = sha256 of (adapter, base_url host, model, messages, sampling, thinking,
benchmark, version). Two requests producing the same key get the same response.

Storage layout:
    <cache_root>/responses/<key[:2]>/<key>.json

Each file holds:
    {
      "key": "<sha256>",
      "saved_at": "2026-05-03T12:34:56Z",
      "response": <ChatResponse.model_dump()>
    }

`cache_hit=True` is set on the loaded response, and `latency_ms` is reset to 0
so timing aggregates aren't polluted by hit replays.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from llm_evalbox.cache.store import cache_root
from llm_evalbox.core.messages import Message
from llm_evalbox.core.request import ChatResponse

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _host_of(base_url: str) -> str:
    try:
        h = httpx.URL(base_url).host
        if h:
            return h
    except Exception:
        pass
    # Fallback: strip scheme/path
    return re.sub(r"^https?://", "", base_url).split("/", 1)[0]


def cache_key(
    *,
    adapter_name: str,
    base_url: str,
    model: str,
    messages: list[Message],
    sampling: dict[str, Any],
    thinking_mode: str,
    benchmark_name: str,
    benchmark_version: str = "v1",
) -> str:
    """Stable sha256 over the parts that affect a model's reply.

    Notes:
      - We use the host (not full base_url) so paths like /v1 vs /v1/ don't
        produce different keys for the same gateway.
      - `sampling` should already be normalized (None values stripped) by
        the caller so two equivalent runs hash identically.
    """
    payload = {
        "adapter": adapter_name,
        "host": _host_of(base_url),
        "model": model,
        "messages": [m.model_dump() for m in messages],
        "sampling": {k: v for k, v in (sampling or {}).items() if v is not None},
        "thinking": thinking_mode,
        "bench": benchmark_name,
        "version": benchmark_version,
    }
    s = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@dataclass
class ResponseCache:
    """File-backed response cache. Disable by passing `enabled=False`."""

    enabled: bool = True
    root: Path | None = None

    def __post_init__(self) -> None:
        if self.root is None:
            self.root = cache_root() / "responses"
        if self.enabled:
            self.root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> ResponseCache:
        """Honor `EVALBOX_NO_CACHE=1` to short-circuit."""
        enabled = os.environ.get("EVALBOX_NO_CACHE") not in ("1", "true", "yes", "on")
        return cls(enabled=enabled)

    def _path(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json"

    def get(self, key: str) -> ChatResponse | None:
        if not self.enabled:
            return None
        p = self._path(key)
        if not p.exists():
            return None
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("cache: failed to read %s: %s", p, e)
            return None
        try:
            resp = ChatResponse(**data["response"])
        except Exception as e:
            logger.warning("cache: malformed entry %s: %s", p, e)
            return None
        # Mark as cache hit; reset latency so aggregates aren't skewed by replay.
        resp.cache_hit = True
        resp.latency_ms = 0.0
        return resp

    def put(self, key: str, response: ChatResponse) -> None:
        if not self.enabled:
            return
        p = self._path(key)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "key": key,
                "saved_at": _utc_now_iso(),
                "response": response.model_dump(),
            }
            tmp = p.with_suffix(".part")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            os.replace(tmp, p)
        except OSError as e:
            logger.warning("cache: failed to write %s: %s", p, e)
