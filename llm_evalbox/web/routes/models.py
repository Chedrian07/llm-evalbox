# SPDX-License-Identifier: Apache-2.0
"""GET /api/models — proxy to the configured endpoint's /v1/models."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from llm_evalbox.adapters import resolve_adapter
from llm_evalbox.adapters.auth import resolve_api_key
from llm_evalbox.core.exceptions import EvalBoxError
from llm_evalbox.core.request import ModelInfo
from llm_evalbox.web.schemas import ConnectionRequest

router = APIRouter()


def _normalize_models(
    models: list[ModelInfo],
    *,
    preferred_model: str | None = None,
) -> list[dict[str, Any]]:
    """Stable, UI-friendly model list.

    Gateways sometimes return duplicate aliases or arbitrary ordering. The web
    UI works better when the currently configured model is surfaced first and
    the rest are deterministic.
    """
    preferred = (preferred_model or "").strip()
    seen: dict[str, dict[str, Any]] = {}
    for model in models:
        model_id = (model.id or "").strip()
        if not model_id or model_id in seen:
            continue
        seen[model_id] = {
            "id": model_id,
            "owned_by": model.owned_by,
            "created": model.created,
        }

    out = list(seen.values())
    out.sort(key=lambda m: (m["id"] != preferred, str(m["id"]).lower()))
    return out


async def _list_models(
    *,
    base_url: str,
    adapter: str,
    api_key: str | None,
    preferred_model: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> list[dict]:
    a = resolve_adapter(
        kind=adapter,
        base_url=base_url,
        api_key=api_key,
        extra_headers=extra_headers or {},
    )
    try:
        models = await a.list_models()
    except EvalBoxError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    finally:
        await a.close()
    return _normalize_models(models, preferred_model=preferred_model)


@router.get("/api/models")
async def list_models(
    base_url: str = Query(...),
    adapter: str = Query("auto"),
    model: str | None = Query(None),
    api_key_env: str | None = Query(None),
) -> list[dict]:
    api_key = resolve_api_key(api_key_env)
    return await _list_models(
        base_url=base_url,
        adapter=adapter,
        api_key=api_key,
        preferred_model=model,
    )


@router.post("/api/models")
async def list_models_post(req: ConnectionRequest) -> list[dict]:
    """List models with the same secret-handling path as connection tests.

    GET /api/models stays for simple env-key usage. The SPA uses POST so a
    user-entered API key is sent in the request body rather than leaking into a
    query string, browser history, or proxy logs.
    """
    api_key = req.api_key or resolve_api_key(req.api_key_env)
    return await _list_models(
        base_url=req.base_url,
        adapter=req.adapter,
        api_key=api_key,
        preferred_model=req.model,
        extra_headers=req.extra_headers,
    )
