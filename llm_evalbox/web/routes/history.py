# SPDX-License-Identifier: Apache-2.0
"""/api/history — list, update, delete runs from the persistent SQLite store."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from llm_evalbox.cache import clear_runs as _clear
from llm_evalbox.cache import delete_run as _delete
from llm_evalbox.cache import get_run as _get
from llm_evalbox.cache import list_runs as _list
from llm_evalbox.cache.history import update_run_meta as _update_meta

router = APIRouter()


class HistoryMetaPatch(BaseModel):
    tags: list[str] | None = None
    notes: str | None = None
    starred: bool | None = None


@router.get("/api/history")
def list_history(
    limit: int = Query(100, ge=1, le=1000),
    model: str | None = Query(None),
    starred: bool = Query(False),
    tag: str | None = Query(None),
) -> list[dict]:
    return _list(limit=limit, model=model, starred_only=starred, tag=tag)


@router.get("/api/history/{run_id}")
def get_history(run_id: str) -> dict:
    payload = _get(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="run not in history")
    return payload


@router.patch("/api/history/{run_id}")
def patch_history(run_id: str, patch: HistoryMetaPatch) -> dict[str, bool]:
    """Partial update of tags / notes / starred. Fields left as null are
    untouched. Returns whether the row existed (and therefore was modified)."""
    ok = _update_meta(
        run_id,
        tags=patch.tags,
        notes=patch.notes,
        starred=patch.starred,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="run not in history")
    return {"updated": True}


@router.delete("/api/history/{run_id}")
def delete_history(run_id: str) -> dict[str, str]:
    if not _delete(run_id):
        raise HTTPException(status_code=404, detail="run not in history")
    return {"status": "deleted"}


@router.delete("/api/history")
def clear_history() -> dict[str, int]:
    return {"deleted": _clear()}
