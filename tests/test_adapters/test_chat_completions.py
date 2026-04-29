# SPDX-License-Identifier: Apache-2.0
"""ChatCompletionsAdapter round-trip with respx-mocked HTTP."""

from __future__ import annotations

import httpx
import pytest
import respx

from llm_evalbox.adapters.chat_completions import ChatCompletionsAdapter
from llm_evalbox.core.exceptions import AuthError, BadRequestError
from llm_evalbox.core.messages import Message
from llm_evalbox.core.request import ChatRequest


@pytest.mark.asyncio
@respx.mock
async def test_basic_round_trip(chat_completion_payload):
    route = respx.post("https://api.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=chat_completion_payload)
    )
    a = ChatCompletionsAdapter("https://api.test/v1", api_key="sk-x")
    req = ChatRequest(model="gpt-4o-mini", messages=[Message(role="user", content="hi")])
    resp = await a.chat(req)
    await a.close()
    assert route.called
    assert resp.text == "B"
    assert resp.usage.prompt_tokens == 10
    assert resp.usage.completion_tokens == 1
    assert resp.thinking_observed is False


@pytest.mark.asyncio
@respx.mock
async def test_thinking_split(chat_completion_with_thinking):
    respx.post("https://api.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=chat_completion_with_thinking)
    )
    a = ChatCompletionsAdapter("https://api.test/v1", api_key="sk-x")
    req = ChatRequest(
        model="deepseek-r1",
        messages=[Message(role="user", content="hi")],
        thinking="auto",
    )
    resp = await a.chat(req)
    await a.close()
    assert resp.thinking_observed is True
    assert "Answer: A" in resp.text
    assert "<think>" not in resp.text
    assert "let me think" in resp.reasoning_text
    assert "more reasoning" in resp.reasoning_text
    assert resp.usage.reasoning_tokens == 4
    assert resp.usage.cached_prompt_tokens == 8


@pytest.mark.asyncio
@respx.mock
async def test_auth_error_immediate():
    respx.post("https://api.test/v1/chat/completions").mock(
        return_value=httpx.Response(401, text='{"error":"bad key"}')
    )
    a = ChatCompletionsAdapter("https://api.test/v1", api_key="sk-x", max_attempts=1)
    req = ChatRequest(model="gpt-4o-mini", messages=[Message(role="user", content="hi")])
    with pytest.raises(AuthError):
        await a.chat(req)
    await a.close()


@pytest.mark.asyncio
@respx.mock
async def test_bad_request_immediate():
    respx.post("https://api.test/v1/chat/completions").mock(
        return_value=httpx.Response(400, text="invalid model")
    )
    a = ChatCompletionsAdapter("https://api.test/v1", api_key="sk-x", max_attempts=1)
    req = ChatRequest(model="gpt-4o-mini", messages=[Message(role="user", content="hi")])
    with pytest.raises(BadRequestError):
        await a.chat(req)
    await a.close()


@pytest.mark.asyncio
@respx.mock
async def test_o_series_uses_max_completion_tokens(chat_completion_payload):
    captured = {}

    def _capture(request):
        import json as _j
        captured["body"] = _j.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json=chat_completion_payload)

    respx.post("https://api.test/v1/chat/completions").mock(side_effect=_capture)
    a = ChatCompletionsAdapter("https://api.test/v1", api_key="sk-x")
    req = ChatRequest(
        model="o1-mini",
        messages=[Message(role="user", content="hi")],
        max_tokens=500,
        temperature=0.0,  # should be stripped by capability
    )
    await a.chat(req)
    await a.close()
    body = captured["body"]
    assert "max_completion_tokens" in body
    assert "max_tokens" not in body
    assert "temperature" not in body  # stripped


@pytest.mark.asyncio
@respx.mock
async def test_qwen3_thinking_on_sets_chat_template_kwargs(chat_completion_payload):
    captured = {}

    def _capture(request):
        import json as _j
        captured["body"] = _j.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json=chat_completion_payload)

    respx.post("https://api.test/v1/chat/completions").mock(side_effect=_capture)
    a = ChatCompletionsAdapter("https://api.test/v1", api_key=None)
    req = ChatRequest(
        model="Qwen/Qwen3-32B",
        messages=[Message(role="user", content="hi")],
        thinking="on",
        max_tokens=512,
    )
    await a.chat(req)
    await a.close()
    body = captured["body"]
    ct = body.get("chat_template_kwargs", {})
    assert ct.get("enable_thinking") is True
    # thinking on bumps max_tokens to at least THINKING_MIN_TOKENS
    assert body["max_tokens"] >= 8192
