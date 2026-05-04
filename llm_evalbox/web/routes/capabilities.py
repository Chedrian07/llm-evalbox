# SPDX-License-Identifier: Apache-2.0
"""/api/capabilities — read & forget the SQLite-backed learned-capability store."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from llm_evalbox.adapters.learned import clear as _clear
from llm_evalbox.adapters.learned import forget as _forget
from llm_evalbox.adapters.learned import list_all as _list_all

router = APIRouter()


@router.get("/api/capabilities")
def list_capabilities() -> list[dict]:
    """Return every learned-capability entry, newest first."""
    return _list_all()


@router.delete("/api/capabilities/{model}")
def forget_capability(model: str) -> dict[str, bool]:
    if not _forget(model):
        raise HTTPException(status_code=404, detail="model not in learned-capabilities")
    return {"forgotten": True}


@router.delete("/api/capabilities")
def clear_capabilities() -> dict[str, int]:
    return {"deleted": _clear()}
