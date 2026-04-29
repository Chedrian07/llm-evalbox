# SPDX-License-Identifier: Apache-2.0
"""OpenAI-compatible /v1/chat/completions adapter.

Serializes `ChatRequest` → wire body, applies capability strip, applies thinking
encoding, sends via httpx, normalizes the response (including reasoning content
and cached/reasoning token accounting).
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from llm_evalbox.adapters.base import ChatAdapter
from llm_evalbox.adapters.capabilities import (
    Capability,
    capability_for,
    strip_unsupported_keys,
)
from llm_evalbox.adapters.retry import retry_policy
from llm_evalbox.core.exceptions import (
    AuthError,
    BadRequestError,
    NetworkError,
    RateLimitError,
)
from llm_evalbox.core.request import ChatRequest, ChatResponse, ModelInfo, Usage
from llm_evalbox.core.thinking import (
    ThinkingMode,
    apply_thinking_to_request,
    parse_thinking,
    thinking_token_budget,
)

logger = logging.getLogger(__name__)


class ChatCompletionsAdapter(ChatAdapter):
    name = "chat_completions"

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        timeout: float = 120.0,
        extra_headers: dict[str, str] | None = None,
        max_attempts: int = 6,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.extra_headers = dict(extra_headers or {})
        self.max_attempts = max_attempts
        self._client: httpx.AsyncClient | None = None

    def _client_lazy(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {
                "User-Agent": "llm-evalbox",
                "Content-Type": "application/json",
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            headers.update(self.extra_headers)
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                http2=False,  # http2 sometimes flaky on local gateways
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------ build
    def _build_body(self, req: ChatRequest, cap: Capability) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": req.model,
            "messages": [m.model_dump() for m in req.messages],
        }

        # max_tokens vs max_completion_tokens (o-series / gpt-5)
        token_budget = req.max_tokens
        thinking_on = req.thinking == ThinkingMode.ON.value
        token_budget = thinking_token_budget(
            base_max_tokens=token_budget,
            model=req.model,
            thinking_on=thinking_on,
        )
        if cap.use_max_completion_tokens:
            body["max_completion_tokens"] = token_budget
        else:
            body["max_tokens"] = token_budget

        # Standard sampling keys (capability layer will strip what's unsupported)
        body["temperature"] = req.temperature
        if req.top_p is not None:
            body["top_p"] = req.top_p
        if req.top_k is not None:
            body["top_k"] = req.top_k
        if req.stop is not None:
            body["stop"] = req.stop
        if req.seed is not None:
            body["seed"] = req.seed
        if req.presence_penalty is not None:
            body["presence_penalty"] = req.presence_penalty
        if req.frequency_penalty is not None:
            body["frequency_penalty"] = req.frequency_penalty
        if req.repetition_penalty is not None:
            body["repetition_penalty"] = req.repetition_penalty
        if req.response_format is not None:
            body["response_format"] = req.response_format

        # Thinking encoding: mutate chat_template_kwargs / reasoning_effort / extra
        ct, re_eff, ex, warns = apply_thinking_to_request(
            model=req.model,
            mode=req.thinking,
            chat_template_kwargs=req.chat_template_kwargs,
            reasoning_effort=req.reasoning_effort,
            extra=req.extra,
        )
        for w in warns:
            logger.warning(w)

        if ct:
            body["chat_template_kwargs"] = ct
        if re_eff is not None:
            body["reasoning_effort"] = re_eff
        if ex:
            for k, v in ex.items():
                body.setdefault(k, v)

        body = strip_unsupported_keys(body, cap, user_drop=req.drop_params)
        return body

    # ------------------------------------------------------------------- send
    async def _send(self, body: dict[str, Any]) -> tuple[dict[str, Any], float, str | None]:
        client = self._client_lazy()
        started = time.perf_counter()
        try:
            r = await client.post("/chat/completions", json=body)
        except httpx.TimeoutException as e:
            raise NetworkError(f"timeout: {e}") from e
        except httpx.NetworkError as e:
            raise NetworkError(f"network: {e}") from e
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        if r.status_code == 401 or r.status_code == 403:
            raise AuthError(_short_body(r), status_code=r.status_code)
        if r.status_code == 429:
            ra = r.headers.get("retry-after")
            try:
                ra_f = float(ra) if ra is not None else None
            except ValueError:
                ra_f = None
            raise RateLimitError(_short_body(r), retry_after=ra_f)
        if 400 <= r.status_code < 500:
            raise BadRequestError(_short_body(r), status_code=r.status_code)
        if r.status_code >= 500:
            raise NetworkError(_short_body(r), status_code=r.status_code)

        try:
            data = r.json()
        except ValueError as e:
            raise NetworkError(f"non-json response: {e}") from e

        return data, elapsed_ms, r.headers.get("x-request-id")

    # ------------------------------------------------------------------- chat
    async def chat(self, req: ChatRequest) -> ChatResponse:
        cap = capability_for(req.model)
        body = self._build_body(req, cap)

        async for attempt in retry_policy(self.max_attempts):
            with attempt:
                data, elapsed_ms, rid = await self._send(body)

        return _normalize_response(data, elapsed_ms, rid)

    async def list_models(self) -> list[ModelInfo]:
        client = self._client_lazy()
        try:
            r = await client.get("/models")
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            raise NetworkError(f"/models: {e}") from e
        if r.status_code == 404 or r.status_code == 405:
            return []
        if r.status_code >= 400:
            raise BadRequestError(_short_body(r), status_code=r.status_code)
        try:
            data = r.json()
        except ValueError:
            return []
        items = data.get("data", []) if isinstance(data, dict) else []
        out: list[ModelInfo] = []
        for it in items:
            if isinstance(it, dict) and isinstance(it.get("id"), str):
                out.append(
                    ModelInfo(
                        id=it["id"],
                        owned_by=it.get("owned_by"),
                        created=it.get("created"),
                    )
                )
        return out


def _short_body(r: httpx.Response) -> str:
    try:
        body = r.text
    except Exception:
        body = ""
    if len(body) > 500:
        body = body[:500] + "..."
    return f"HTTP {r.status_code}: {body}"


def _normalize_response(
    data: dict[str, Any], latency_ms: float, request_id: str | None
) -> ChatResponse:
    """Convert chat-completions JSON → ChatResponse, splitting reasoning/thinking."""
    choices = data.get("choices") or []
    if not choices:
        raw_text = ""
        finish_reason = "error"
    else:
        msg = choices[0].get("message") or {}
        raw_text = msg.get("content") or ""
        finish_reason = choices[0].get("finish_reason") or "stop"

    text, reasoning_text, observed = parse_thinking(raw_text, data)

    usage_in = data.get("usage") or {}
    pt = int(usage_in.get("prompt_tokens", 0) or 0)
    ct = int(usage_in.get("completion_tokens", 0) or 0)
    tt = int(usage_in.get("total_tokens", 0) or (pt + ct))

    cached = 0
    pdetails = usage_in.get("prompt_tokens_details") or {}
    if isinstance(pdetails, dict):
        cached = int(pdetails.get("cached_tokens", 0) or 0)

    reasoning_tok = 0
    cdetails = usage_in.get("completion_tokens_details") or {}
    if isinstance(cdetails, dict):
        reasoning_tok = int(cdetails.get("reasoning_tokens", 0) or 0)

    reasoning_estimated = False
    if observed and reasoning_tok == 0 and reasoning_text:
        # Provider didn't report reasoning_tokens but we observed thinking content.
        # Estimate so cost/UI doesn't show 0; flag as estimated.
        reasoning_tok = max(1, len(reasoning_text) // 3)
        reasoning_estimated = True

    return ChatResponse(
        text=text,
        raw_text=raw_text,
        reasoning_text=reasoning_text,
        finish_reason=finish_reason,
        usage=Usage(
            prompt_tokens=pt,
            completion_tokens=ct,
            reasoning_tokens=reasoning_tok,
            cached_prompt_tokens=cached,
            total_tokens=tt,
            reasoning_estimated=reasoning_estimated,
        ),
        latency_ms=latency_ms,
        provider_request_id=request_id,
        raw=data,
        thinking_observed=observed,
    )
