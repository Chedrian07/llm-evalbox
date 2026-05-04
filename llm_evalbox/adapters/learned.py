# SPDX-License-Identifier: Apache-2.0
"""Persistent store of doctor-learned drop_params per model.

Stored as `~/.config/llm-evalbox/learned_capabilities.json`:

    {
      "version": 1,
      "models": {
        "gpt-5.4-mini": {"drop_params": ["reasoning_effort"], "learned_at": "..."},
        "o3-mini":      {"drop_params": ["temperature"],      "learned_at": "..."}
      }
    }

Doctor and `evalbox run` consult this file at startup and merge the matching
entry into `req.drop_params` so the second time around the keys are stripped
before they hit the wire.

Match rule: an exact `model` key wins; failing that, the first stored model
that is a substring of the runtime model wins (so `gpt-5.4-mini` learned
once also covers `gpt-5.4-mini-2026-01-01`).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_evalbox.cache.store import config_root

logger = logging.getLogger(__name__)

_VERSION = 1


def store_path() -> Path:
    return config_root() / "learned_capabilities.json"


def _load() -> dict[str, Any]:
    p = store_path()
    if not p.exists():
        return {"version": _VERSION, "models": {}}
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "models" not in data:
            return {"version": _VERSION, "models": {}}
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("failed to read %s: %s", p, e)
        return {"version": _VERSION, "models": {}}


def _save(data: dict[str, Any]) -> None:
    p = store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".part")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def remember(model: str, drop_params: list[str]) -> None:
    """Add (or refresh) a model entry. Idempotent + monotone (we only ever
    add to the set; capabilities don't usually un-restrict)."""
    if not model or not drop_params:
        return
    data = _load()
    models = data.setdefault("models", {})
    existing = models.get(model, {})
    existing_keys = set(existing.get("drop_params") or [])
    new_keys = sorted(existing_keys.union(drop_params))
    models[model] = {
        "drop_params": new_keys,
        "learned_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    _save(data)


def lookup(model: str) -> list[str]:
    """Return the union of drop_params for any stored model that matches."""
    data = _load()
    models = data.get("models") or {}
    if model in models:
        return list(models[model].get("drop_params") or [])
    # Fallback: substring match (longest first wins, so more specific entries
    # override less specific ones).
    candidates = sorted(models.keys(), key=len, reverse=True)
    for k in candidates:
        if k and k in model:
            return list(models[k].get("drop_params") or [])
    return []


def list_all() -> list[dict[str, Any]]:
    data = _load()
    out = []
    for k, v in (data.get("models") or {}).items():
        out.append({
            "model": k,
            "drop_params": list(v.get("drop_params") or []),
            "learned_at": v.get("learned_at", ""),
        })
    return sorted(out, key=lambda r: r.get("learned_at", ""), reverse=True)


def forget(model: str) -> bool:
    data = _load()
    models = data.get("models") or {}
    if model not in models:
        return False
    del models[model]
    _save(data)
    return True


def clear() -> int:
    data = _load()
    n = len(data.get("models") or {})
    data["models"] = {}
    _save(data)
    return n
