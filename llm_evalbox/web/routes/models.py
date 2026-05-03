# SPDX-License-Identifier: Apache-2.0
"""GET /api/models — proxy to the configured endpoint's /v1/models."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from llm_evalbox.adapters import resolve_adapter
from llm_evalbox.adapters.auth import resolve_api_key
from llm_evalbox.core.exceptions import EvalBoxError

router = APIRouter()


@router.get("/api/models")
async def list_models(
    base_url: str = Query(...),
    adapter: str = Query("auto"),
    api_key_env: str | None = Query(None),
) -> list[dict]:
    api_key = resolve_api_key(api_key_env)
    a = resolve_adapter(kind=adapter, base_url=base_url, api_key=api_key)
    try:
        models = await a.list_models()
    except EvalBoxError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    finally:
        await a.close()
    return [{"id": m.id, "owned_by": m.owned_by, "created": m.created} for m in models]
