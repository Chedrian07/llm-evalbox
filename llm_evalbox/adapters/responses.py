# SPDX-License-Identifier: Apache-2.0
"""OpenAI Responses (`/v1/responses`) adapter.

Targets OpenAI's o-series / gpt-5 / gpt-oss families and any gateway that
implements the same shape. Most non-OpenAI gateways do NOT expose this route —
use chat-completions for them.

Differences from `chat_completions.py`:
  - Wire payload uses `input` (list of typed items) instead of `messages`.
  - Token budget uses `max_output_tokens` instead of `max_tokens` /
    `max_completion_tokens`.
  - Reasoning controlled via `reasoning.effort` (object, not bare key).
  - Response payload uses `output[]` with `type=="message"` / `"reasoning"` /
    `"function_call"`.
  - Usage carries `input_tokens` / `output_tokens` (+ `*_tokens_details`).
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


class ResponsesAdapter(ChatAdapter):
    name = "responses"

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
                http2=False,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------ build
    def _build_body(self, req: ChatRequest, cap: Capability) -> dict[str, Any]:
        # messages → input items
        input_items = [
            {
                "type": "message",
                "role": m.role,
                "content": [{"type": "input_text", "text": m.content}],
            }
            for m in req.messages
        ]
        body: dict[str, Any] = {"model": req.model, "input": input_items}

        # max_output_tokens (Responses) — clamp when thinking is on
        thinking_on = req.thinking == ThinkingMode.ON.value
        token_budget = thinking_token_budget(
            base_max_tokens=req.max_tokens,
            model=req.model,
            thinking_on=thinking_on,
        )
        body["max_output_tokens"] = token_budget

        # Sampling — Responses also accepts these on supported models.
        body["temperature"] = req.temperature
        if req.top_p is not None:
            body["top_p"] = req.top_p
        if req.top_k is not None:
            body["top_k"] = req.top_k
        if req.stop is not None:
            body["stop"] = req.stop
        if req.seed is not None:
            body["seed"] = req.seed
        # presence/frequency/repetition penalties are typically rejected by
        # the o-series — capability strip below removes them.
        if req.presence_penalty is not None:
            body["presence_penalty"] = req.presence_penalty
        if req.frequency_penalty is not None:
            body["frequency_penalty"] = req.frequency_penalty
        if req.repetition_penalty is not None:
            body["repetition_penalty"] = req.repetition_penalty
        if req.response_format is not None:
            # Responses uses `text.format`, but capability strip handles missing
            # support; we forward whatever was set.
            body["text"] = {"format": req.response_format}

        # Thinking encoding: for Responses families we get back reasoning_effort
        # which becomes `reasoning.effort` (nested object).
        ct, re_eff, ex, warns = apply_thinking_to_request(
            model=req.model,
            mode=req.thinking,
            chat_template_kwargs=req.chat_template_kwargs,
            reasoning_effort=req.reasoning_effort,
            extra=req.extra,
        )
        for w in warns:
            logger.warning(w)

        if re_eff is not None:
            body["reasoning"] = {"effort": re_eff}
        # chat_template_kwargs is a vLLM/SGLang concept — Responses ignores it,
        # but we forward via extra so any custom proxy may pick it up.
        if ct:
            body.setdefault("chat_template_kwargs", ct)
        for k, v in ex.items():
            body.setdefault(k, v)

        # Capability strip uses the same key set as chat-completions; the
        # adapter-side rename of max_tokens → max_output_tokens already happened.
        body = strip_unsupported_keys(body, cap, user_drop=req.drop_params)
        if body.get("reasoning") and (
            not cap.accepts_reasoning_effort
            or "reasoning_effort" in set(req.drop_params or [])
        ):
            body.pop("reasoning", None)
        return body

    # ------------------------------------------------------------------- send
    async def _send(self, body: dict[str, Any]) -> tuple[dict[str, Any], float, str | None]:
        client = self._client_lazy()
        started = time.perf_counter()
        try:
            r = await client.post("/responses", json=body)
        except httpx.TimeoutException as e:
            raise NetworkError(f"timeout: {e}") from e
        except httpx.NetworkError as e:
            raise NetworkError(f"network: {e}") from e
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        if r.status_code in (401, 403):
            raise AuthError(_short_body(r), status_code=r.status_code)
        if r.status_code == 429:
            ra = r.headers.get("retry-after")
            try:
                ra_f = float(ra) if ra is not None else None
            except ValueError:
                ra_f = None
            raise RateLimitError(_short_body(r), retry_after=ra_f)
        if r.status_code in (404, 405):
            # Specific guidance — common confusion when a gateway only exposes chat.
            raise BadRequestError(
                f"{_short_body(r)}\n"
                "  hint: this endpoint does not expose /v1/responses. "
                "Use --adapter chat (or --adapter auto).",
                status_code=r.status_code,
            )
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
        if r.status_code in (404, 405):
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
    """Convert Responses JSON → ChatResponse.

    `data["output"]` is a list of typed items:
      - {"type": "message", "content": [{"type": "output_text"|"text", "text": ...}]}
      - {"type": "reasoning", "summary"|"content": [{"type": "...", "text": ...}]}
      - {"type": "function_call", ...}     # ignored until M4
    """
    text_parts: list[str] = []
    reasoning_parts: list[str] = []
    finish_reason = "stop"

    for item in data.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        t = item.get("type")
        if t == "message":
            for c in item.get("content", []) or []:
                if isinstance(c, dict) and c.get("type") in ("output_text", "text"):
                    txt = c.get("text", "")
                    if isinstance(txt, str):
                        text_parts.append(txt)
        elif t == "reasoning":
            for sub_key in ("summary", "content"):
                for sub in item.get(sub_key, []) or []:
                    if isinstance(sub, dict):
                        txt = sub.get("text")
                        if isinstance(txt, str) and txt.strip():
                            reasoning_parts.append(txt)
        elif t == "function_call":
            logger.warning("Responses function_call output ignored (tool-use is M4)")

    raw_text = "\n".join(text_parts)
    # parse_thinking handles think-tag / <thinking> tags as well; we feed it the
    # same `data` so its Responses-aware branch can pick up any reasoning items
    # we might have missed (defensive — we already extracted above).
    visible, parsed_reasoning, observed = parse_thinking(raw_text, data)

    # Combine reasoning from explicit items + tag-stripped fragments.
    if parsed_reasoning and parsed_reasoning not in reasoning_parts:
        reasoning_parts.append(parsed_reasoning)
    reasoning_text = "\n\n".join(p for p in reasoning_parts if p)
    text = visible if visible else raw_text

    if data.get("status") == "incomplete":
        finish_reason = "length"
    elif data.get("status") == "failed":
        finish_reason = "error"

    usage_in = data.get("usage") or {}
    pt = int(usage_in.get("input_tokens", 0) or 0)
    ct = int(usage_in.get("output_tokens", 0) or 0)
    tt = int(usage_in.get("total_tokens", 0) or (pt + ct))

    cached = 0
    idetails = usage_in.get("input_tokens_details") or {}
    if isinstance(idetails, dict):
        cached = int(idetails.get("cached_tokens", 0) or 0)

    reasoning_tok = 0
    odetails = usage_in.get("output_tokens_details") or {}
    if isinstance(odetails, dict):
        reasoning_tok = int(odetails.get("reasoning_tokens", 0) or 0)

    reasoning_estimated = False
    if reasoning_text and reasoning_tok == 0:
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
        thinking_observed=observed or bool(reasoning_parts),
    )
