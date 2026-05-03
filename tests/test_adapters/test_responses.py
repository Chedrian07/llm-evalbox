# SPDX-License-Identifier: Apache-2.0
"""ResponsesAdapter round-trip with respx-mocked /v1/responses."""

from __future__ import annotations

import httpx
import pytest
import respx

from llm_evalbox.adapters.responses import ResponsesAdapter
from llm_evalbox.core.exceptions import BadRequestError
from llm_evalbox.core.messages import Message
from llm_evalbox.core.request import ChatRequest


def _basic_responses_payload() -> dict:
    return {
        "id": "resp_test",
        "object": "response",
        "model": "o3-mini",
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "B"}],
            }
        ],
        "usage": {
            "input_tokens": 12,
            "output_tokens": 1,
            "total_tokens": 13,
            "input_tokens_details": {"cached_tokens": 4},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }


def _payload_with_reasoning() -> dict:
    return {
        "id": "resp_reason",
        "object": "response",
        "model": "o3-mini",
        "status": "completed",
        "output": [
            {
                "type": "reasoning",
                "summary": [{"type": "summary_text", "text": "thought process A"}],
            },
            {
                "type": "reasoning",
                "content": [{"type": "reasoning_text", "text": "more reasoning"}],
            },
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Final: A"}],
            },
        ],
        "usage": {
            "input_tokens": 20,
            "output_tokens": 6,
            "total_tokens": 26,
            "output_tokens_details": {"reasoning_tokens": 5},
        },
    }


@pytest.mark.asyncio
@respx.mock
async def test_basic_round_trip():
    respx.post("https://api.test/v1/responses").mock(
        return_value=httpx.Response(200, json=_basic_responses_payload())
    )
    a = ResponsesAdapter("https://api.test/v1", api_key="sk-x")
    req = ChatRequest(model="o3-mini", messages=[Message(role="user", content="hi")])
    resp = await a.chat(req)
    await a.close()
    assert resp.text == "B"
    assert resp.usage.prompt_tokens == 12
    assert resp.usage.completion_tokens == 1
    assert resp.usage.cached_prompt_tokens == 4
    assert resp.thinking_observed is False


@pytest.mark.asyncio
@respx.mock
async def test_reasoning_items_collected():
    respx.post("https://api.test/v1/responses").mock(
        return_value=httpx.Response(200, json=_payload_with_reasoning())
    )
    a = ResponsesAdapter("https://api.test/v1", api_key="sk-x")
    req = ChatRequest(model="o3-mini", messages=[Message(role="user", content="hi")])
    resp = await a.chat(req)
    await a.close()
    assert "Final: A" in resp.text
    assert "thought process A" in resp.reasoning_text
    assert "more reasoning" in resp.reasoning_text
    assert resp.usage.reasoning_tokens == 5
    assert resp.thinking_observed is True


@pytest.mark.asyncio
@respx.mock
async def test_404_message_suggests_chat_adapter():
    respx.post("https://api.test/v1/responses").mock(
        return_value=httpx.Response(404, text="Not Found")
    )
    a = ResponsesAdapter("https://api.test/v1", api_key="sk-x", max_attempts=1)
    req = ChatRequest(model="o3-mini", messages=[Message(role="user", content="hi")])
    with pytest.raises(BadRequestError) as ei:
        await a.chat(req)
    await a.close()
    assert "does not expose /v1/responses" in str(ei.value)


@pytest.mark.asyncio
@respx.mock
async def test_body_serializes_messages_to_input():
    captured = {}

    def _capture(request):
        import json as _j
        captured["body"] = _j.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json=_basic_responses_payload())

    respx.post("https://api.test/v1/responses").mock(side_effect=_capture)
    a = ResponsesAdapter("https://api.test/v1", api_key="sk-x")
    req = ChatRequest(
        model="o3-mini",
        messages=[
            Message(role="system", content="be terse"),
            Message(role="user", content="hi"),
        ],
        max_tokens=128,
        thinking="on",
    )
    await a.chat(req)
    await a.close()
    body = captured["body"]
    # messages → input
    assert "messages" not in body
    assert isinstance(body["input"], list)
    assert body["input"][0]["type"] == "message"
    assert body["input"][0]["role"] == "system"
    assert body["input"][0]["content"][0]["type"] == "input_text"
    # max_output_tokens (not max_tokens / max_completion_tokens)
    assert "max_output_tokens" in body
    assert "max_tokens" not in body
    # thinking on → reasoning.effort set
    assert body["reasoning"]["effort"] in ("high", "medium", "low", "xhigh")


@pytest.mark.asyncio
@respx.mock
async def test_resolve_adapter_responses_returns_responses_adapter():
    from llm_evalbox.adapters import resolve_adapter
    a = resolve_adapter(kind="responses", base_url="https://api.test/v1", api_key="sk")
    assert isinstance(a, ResponsesAdapter)
    await a.close()


@pytest.mark.asyncio
async def test_resolve_adapter_auto_returns_chat_adapter():
    from llm_evalbox.adapters import ChatCompletionsAdapter, resolve_adapter
    a = resolve_adapter(kind="auto", base_url="https://api.test/v1", api_key="sk")
    assert isinstance(a, ChatCompletionsAdapter)
    await a.close()
