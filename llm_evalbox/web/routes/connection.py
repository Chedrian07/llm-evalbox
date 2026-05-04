# SPDX-License-Identifier: Apache-2.0
"""POST /api/connection/test — probe a base_url + model and report capability."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from llm_evalbox.adapters import resolve_adapter
from llm_evalbox.adapters.auth import resolve_api_key
from llm_evalbox.adapters.capabilities import (
    capability_for,
    parse_unsupported_param_error,
)
from llm_evalbox.adapters.url_rewrite import rewrite_localhost
from llm_evalbox.core.exceptions import BadRequestError, EvalBoxError
from llm_evalbox.core.messages import Message
from llm_evalbox.core.request import ChatRequest
from llm_evalbox.web.schemas import (
    CapabilityInfo,
    ConnectionRequest,
    ConnectionResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/connection/test", response_model=ConnectionResponse)
async def test_connection(req: ConnectionRequest) -> ConnectionResponse:
    cap = capability_for(req.model)
    cap_info = CapabilityInfo(
        accepts_temperature=cap.accepts_temperature,
        accepts_top_p=cap.accepts_top_p,
        accepts_top_k=cap.accepts_top_k,
        accepts_seed=cap.accepts_seed,
        accepts_reasoning_effort=cap.accepts_reasoning_effort,
        use_max_completion_tokens=cap.use_max_completion_tokens,
        notes=cap.notes,
    )

    api_key = req.api_key or resolve_api_key(req.api_key_env)
    # Probe the rewrite so the SPA can show "localhost → host.docker.internal"
    # before/after the call. resolve_adapter rewrites internally too — we just
    # need the boolean here.
    rewritten_url, did_rewrite = rewrite_localhost(req.base_url)
    adapter = resolve_adapter(
        kind=req.adapter,
        base_url=req.base_url,  # auto.py rewrites internally; pass the original
        api_key=api_key,
        extra_headers=req.extra_headers,
    )
    effective_base_url = rewritten_url if did_rewrite else None

    model_listed: bool | None = None
    model_count: int | None = None
    try:
        models = await adapter.list_models()
        model_count = len(models)
        if models:
            model_listed = req.model in [m.id for m in models]
    except EvalBoxError as e:
        logger.info("connection.test list_models failed: %s", e)

    drop_params: list[str] = []
    resp = None
    last_error: BadRequestError | None = None
    for _ in range(3):
        chat_req = ChatRequest(
            model=req.model,
            messages=[Message(role="user", content="Reply with the single word: OK")],
            max_tokens=8,
            thinking="auto",
            drop_params=list(drop_params),
        )
        try:
            resp = await adapter.chat(chat_req)
            break
        except BadRequestError as e:
            last_error = e
            unsupported = parse_unsupported_param_error(str(e))
            new = sorted(k for k in unsupported if k not in drop_params)
            if not new:
                break
            drop_params.extend(new)
        except EvalBoxError as e:
            await adapter.close()
            return ConnectionResponse(
                ok=False, adapter=adapter.name,
                model_listed=model_listed, model_count=model_count,
                capability=cap_info, error=str(e),
                effective_base_url=effective_base_url,
            )

    await adapter.close()

    if resp is None:
        return ConnectionResponse(
            ok=False, adapter=adapter.name,
            model_listed=model_listed, model_count=model_count,
            capability=cap_info,
            learned_drop_params=drop_params,
            error=str(last_error) if last_error else "dry chat failed",
            effective_base_url=effective_base_url,
        )

    return ConnectionResponse(
        ok=True,
        adapter=adapter.name,
        model_listed=model_listed,
        model_count=model_count,
        latency_ms=resp.latency_ms,
        finish_reason=resp.finish_reason,
        thinking_observed=resp.thinking_observed,
        text_preview=resp.text[:120],
        capability=cap_info,
        learned_drop_params=drop_params,
        effective_base_url=effective_base_url,
    )
