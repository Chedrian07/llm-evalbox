# SPDX-License-Identifier: Apache-2.0
"""GET /api/history — list runs from the persistent SQLite store."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from llm_evalbox.cache import delete_run as _delete
from llm_evalbox.cache import get_run as _get
from llm_evalbox.cache import list_runs as _list

router = APIRouter()


@router.get("/api/history")
def list_history(
    limit: int = Query(100, ge=1, le=1000),
    model: str | None = Query(None),
) -> list[dict]:
    return _list(limit=limit, model=model)


@router.get("/api/history/{run_id}")
def get_history(run_id: str) -> dict:
    payload = _get(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="run not in history")
    return payload


@router.delete("/api/history/{run_id}")
def delete_history(run_id: str) -> dict[str, str]:
    if not _delete(run_id):
        raise HTTPException(status_code=404, detail="run not in history")
    return {"status": "deleted"}
