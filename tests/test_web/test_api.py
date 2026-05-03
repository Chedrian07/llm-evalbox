# SPDX-License-Identifier: Apache-2.0
"""FastAPI / TestClient round-trips for the M1 routes."""

from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from llm_evalbox.web.server import build_app


@pytest.fixture
def client():
    app = build_app()
    return TestClient(app)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_root_placeholder_when_no_frontend(client):
    r = client.get("/")
    assert r.status_code == 200
    # Either the placeholder HTML or a real index.html — just check it's HTML.
    ct = r.headers.get("content-type", "")
    assert "html" in ct.lower()


def test_list_benchmarks(client):
    r = client.get("/api/benchmarks")
    assert r.status_code == 200
    body = r.json()
    names = {b["name"] for b in body}
    # We expect the 16 we registered
    assert "mmlu" in names
    assert "mbpp" in names
    assert "kmmlu" in names
    cats = {b["category"] for b in body}
    assert "knowledge" in cats
    assert "coding" in cats


def test_pricing_estimate(client):
    r = client.post("/api/pricing/estimate", json={
        "model": "gpt-4o-mini",
        "benchmarks": ["mmlu", "gsm8k"],
        "samples": 100,
        "concurrency": 4,
        "thinking": "off",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["est_prompt_tokens"] > 0
    # gpt-4o-mini is in the catalog → cost should be a number
    assert body["est_cost_usd"] is not None
    assert body["est_seconds"] > 0


@respx.mock
def test_models_post_uses_inline_api_key(client):
    def _handler(request):
        assert request.headers.get("authorization") == "Bearer sk-inline"
        return httpx.Response(200, json={
            "data": [{"id": "fake-model", "owned_by": "test"}]
        })

    respx.get("https://api.test/v1/models").mock(side_effect=_handler)

    r = client.post("/api/models", json={
        "base_url": "https://api.test/v1",
        "model": "fake-model",
        "adapter": "chat_completions",
        "api_key": "sk-inline",
    })
    assert r.status_code == 200
    assert r.json()[0]["id"] == "fake-model"


@respx.mock
def test_connection_ok(client):
    respx.post("https://api.test/v1/chat/completions").mock(return_value=httpx.Response(200, json={
        "id": "x", "model": "gpt-4o-mini",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": "OK"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
    }))
    respx.get("https://api.test/v1/models").mock(return_value=httpx.Response(200, json={
        "data": [{"id": "gpt-4o-mini", "owned_by": "test"}]
    }))

    r = client.post("/api/connection/test", json={
        "base_url": "https://api.test/v1",
        "model": "gpt-4o-mini",
        "adapter": "auto",
        "api_key": "sk-x",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["adapter"] == "chat_completions"
    assert body["model_listed"] is True
    assert body["text_preview"] == "OK"
    assert body["learned_drop_params"] == []


@respx.mock
def test_connection_drops_unsupported_param(client):
    """First call returns 400 with 'level "minimal" not supported'; doctor
    learns drop_params=['reasoning_effort'] and retries successfully."""
    calls = {"n": 0}

    def _handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                400,
                json={"error": {"message": 'level "minimal" not supported, valid levels: low, medium, high, xhigh',
                                "type": "invalid_request_error"}},
            )
        return httpx.Response(200, json={
            "id": "x", "model": "gpt-5-mini",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": "OK"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
        })

    respx.post("https://api.test/v1/chat/completions").mock(side_effect=_handler)
    respx.get("https://api.test/v1/models").mock(return_value=httpx.Response(200, json={"data": []}))

    r = client.post("/api/connection/test", json={
        "base_url": "https://api.test/v1",
        "model": "gpt-5-mini",
        "adapter": "auto",
        "api_key": "sk-x",
        # force reasoning_effort=minimal via api_key route — but we don't expose
        # that here; the test backend rejects regardless of what we send. The
        # key thing is parser learns the keyword from the 4xx and retries.
    })
    assert r.status_code == 200
    body = r.json()
    # The probe in our route doesn't *send* reasoning_effort, so the 4xx
    # parser will learn it but the actual request didn't carry it. Still,
    # the response should be ok=True after the second call.
    assert body["ok"] is True
    assert "reasoning_effort" in body["learned_drop_params"]


@pytest.mark.asyncio
@respx.mock
async def test_runs_lifecycle():
    """End-to-end: POST /api/runs starts a run, polling /api/runs/{id} sees
    completion with the final result payload. Uses AsyncClient + ASGITransport
    so the in-process background task and the polling loop share an event loop."""
    import asyncio as _asyncio

    from httpx import ASGITransport, AsyncClient

    respx.post("https://api.test/v1/chat/completions").mock(return_value=httpx.Response(200, json={
        "id": "x", "model": "gpt-4o-mini",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": "B"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
    }))

    app = build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.post("/api/runs", json={
            "connection": {
                "base_url": "https://api.test/v1",
                "model": "gpt-4o-mini",
                "adapter": "chat_completions",
                "api_key": "sk-x",
            },
            "benches": ["mmlu"],
            "samples": 3,
            "concurrency": 2,
            "thinking": "off",
            "no_cache": True,
        })
        assert r.status_code == 200
        rid = r.json()["run_id"]

        detail = None
        for _ in range(200):  # 10s budget
            detail = (await ac.get(f"/api/runs/{rid}")).json()
            if detail["status"] in ("completed", "failed", "cancelled"):
                break
            await _asyncio.sleep(0.05)

        assert detail is not None
        assert detail["status"] == "completed", detail
        assert detail["result"] is not None
        assert detail["result"]["benchmarks"][0]["name"] == "mmlu"


@pytest.mark.asyncio
@respx.mock
async def test_runs_prompt_cache_aware_reaches_benchmark():
    import asyncio as _asyncio

    from httpx import ASGITransport, AsyncClient

    from llm_evalbox.eval._cache_aware import PROMPT_CACHE_PREFIX

    seen_messages: list[list[dict]] = []

    def _handler(request):
        import json as _json
        seen_messages.append(_json.loads(request.content)["messages"])
        return httpx.Response(200, json={
            "id": "x", "model": "gpt-4o-mini",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": "B"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
        })

    respx.post("https://api.test/v1/chat/completions").mock(side_effect=_handler)

    app = build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.post("/api/runs", json={
            "connection": {
                "base_url": "https://api.test/v1",
                "model": "gpt-4o-mini",
                "adapter": "chat_completions",
                "api_key": "sk-x",
            },
            "benches": ["mmlu"],
            "samples": 1,
            "concurrency": 1,
            "thinking": "off",
            "prompt_cache_aware": True,
            "no_cache": True,
        })
        assert r.status_code == 200
        rid = r.json()["run_id"]

        detail = None
        for _ in range(200):
            detail = (await ac.get(f"/api/runs/{rid}")).json()
            if detail["status"] in ("completed", "failed", "cancelled"):
                break
            await _asyncio.sleep(0.05)

    assert detail is not None and detail["status"] == "completed"
    assert seen_messages
    assert seen_messages[0][0]["role"] == "system"
    assert seen_messages[0][0]["content"] == PROMPT_CACHE_PREFIX


@respx.mock
def test_runs_sse_events_streaming(client):
    """SSE stream delivers progress events as the run advances. Avoids the
    full done-loop because TestClient's sync→async bridge can starve the
    background task; checking we get at least one progress event is enough
    to verify the wiring."""

    respx.post("https://api.test/v1/chat/completions").mock(return_value=httpx.Response(200, json={
        "id": "x", "model": "gpt-4o-mini",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": "B"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
    }))

    rid = client.post("/api/runs", json={
        "connection": {
            "base_url": "https://api.test/v1",
            "model": "gpt-4o-mini",
            "adapter": "chat_completions",
            "api_key": "sk-x",
        },
        "benches": ["mmlu"],
        "samples": 2,
        "concurrency": 2,
        "thinking": "off",
        "no_cache": True,
    }).json()["run_id"]

    seen: list[str] = []
    with client.stream("GET", f"/api/runs/{rid}/events", timeout=10) as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if not line:
                continue
            text = line if isinstance(line, str) else line.decode("utf-8", "replace")
            if text.startswith("event:"):
                seen.append(text.split(":", 1)[1].strip())
            # Stop once we've seen anything informative
            if "done" in seen or len(seen) >= 5:
                break

    assert seen, "expected at least one SSE event"
    # First event is loading (progress) — we don't require "done" because
    # TestClient's stream may close before the background task posts it.


def test_unknown_bench_returns_400(client):
    r = client.post("/api/runs", json={
        "connection": {
            "base_url": "https://api.test/v1",
            "model": "gpt-4o-mini",
            "adapter": "chat_completions",
            "api_key": "sk-x",
        },
        "benches": ["does_not_exist"],
        "samples": 3,
    })
    assert r.status_code == 400


def test_bind_token_required():
    """When bind_token is set, /api/* requires X-Evalbox-Token."""
    app = build_app(bind_token="secret-xyz")
    c = TestClient(app)
    # No token → 401
    r = c.get("/api/health")
    assert r.status_code == 401
    # Wrong token → 401
    r = c.get("/api/health", headers={"X-Evalbox-Token": "nope"})
    assert r.status_code == 401
    # Correct token → 200
    r = c.get("/api/health", headers={"X-Evalbox-Token": "secret-xyz"})
    assert r.status_code == 200
