# SPDX-License-Identifier: Apache-2.0
"""POST /api/shares + GET /api/shares/{hash}.

A share record is the result.json + the connection params (host-only,
no api_key) of a finished run. Stored in
`~/.cache/llm-evalbox/shares/<hash>.json`. Anonymous — anyone with the
hash sees the result.

The 12-char hash is derived from sha256 of the canonical JSON, so
duplicates collapse onto the same id.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from llm_evalbox.cache.store import cache_root
from llm_evalbox.web.state import get_registry

logger = logging.getLogger(__name__)
router = APIRouter()


def _shares_dir() -> Path:
    p = cache_root() / "shares"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _scrub(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip anything resembling secrets before persisting."""
    out = dict(payload)
    prov = dict(out.get("provider", {}))
    bu = prov.get("base_url", "")
    # Keep only the host so the share is informative without leaking internal proxies.
    try:
        from urllib.parse import urlparse
        host = urlparse(bu).hostname or bu
        prov["base_url"] = f"https://{host}"
    except Exception:
        prov["base_url"] = "<scrubbed>"
    out["provider"] = prov
    return out


@router.post("/api/shares")
def create_share(body: dict[str, Any]) -> dict[str, str]:
    run_id = body.get("run_id")
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id required")
    state = get_registry().get(run_id)
    if state is None or state.final_payload is None:
        raise HTTPException(status_code=404, detail="run not finished or not found")

    payload = _scrub(state.final_payload)
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    h = hashlib.sha256(canonical).hexdigest()[:12]

    p = _shares_dir() / f"{h}.json"
    if not p.exists():
        with open(p, "w", encoding="utf-8") as f:
            f.write(canonical.decode("utf-8"))
    return {"hash": h, "url": f"/api/shares/{h}"}


@router.get("/api/shares/{share_hash}")
def get_share(share_hash: str) -> dict[str, Any]:
    if not share_hash or not share_hash.isalnum():
        raise HTTPException(status_code=400, detail="bad hash")
    p = _shares_dir() / f"{share_hash}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="share not found")
    with open(p, encoding="utf-8") as f:
        return json.load(f)
