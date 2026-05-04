# SPDX-License-Identifier: Apache-2.0
"""POST /api/connection/test — verify localhost auto-rewrite end-to-end.

Simulates the container case via `EVALBOX_IN_DOCKER=1` and confirms:
  - the outbound HTTP call goes to host.docker.internal (not localhost)
  - the response carries `effective_base_url` so the SPA can show its chip
  - the user's input `base_url` is preserved in the response (no mutation)
"""

from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from llm_evalbox.web.server import build_app


@pytest.fixture
def client():
    return TestClient(build_app())


@respx.mock
def test_localhost_rewritten_inside_container(client, monkeypatch):
    monkeypatch.setenv("EVALBOX_IN_DOCKER", "1")
    monkeypatch.delenv("EVALBOX_LOCALHOST_REWRITE", raising=False)

    # If our rewrite works, the call lands on host.docker.internal.
    respx.post("http://host.docker.internal:8000/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "x",
                "model": "local-llm",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "OK"},
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
            },
        )
    )
    respx.get("http://host.docker.internal:8000/v1/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "local-llm"}]})
    )

    r = client.post(
        "/api/connection/test",
        json={
            "base_url": "http://localhost:8000/v1",
            "model": "local-llm",
            "adapter": "auto",
            "api_key": "sk-test",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["effective_base_url"] == "http://host.docker.internal:8000/v1"


@respx.mock
def test_no_rewrite_outside_container(client, monkeypatch):
    monkeypatch.delenv("EVALBOX_IN_DOCKER", raising=False)
    monkeypatch.setenv("EVALBOX_LOCALHOST_REWRITE", "auto")

    respx.post("http://localhost:8000/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "x",
                "model": "local-llm",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "OK"},
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
            },
        )
    )
    respx.get("http://localhost:8000/v1/models").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    r = client.post(
        "/api/connection/test",
        json={
            "base_url": "http://localhost:8000/v1",
            "model": "local-llm",
            "adapter": "auto",
            "api_key": "sk-test",
        },
    )
    assert r.status_code == 200
    # `effective_base_url` is null when no rewrite happened — frontend hides chip.
    assert r.json()["effective_base_url"] is None


@respx.mock
def test_kill_switch_disables_rewrite(client, monkeypatch):
    monkeypatch.setenv("EVALBOX_IN_DOCKER", "1")
    monkeypatch.setenv("EVALBOX_LOCALHOST_REWRITE", "off")

    respx.post("http://localhost:8000/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "x",
                "model": "local-llm",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "OK"},
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
            },
        )
    )
    respx.get("http://localhost:8000/v1/models").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    r = client.post(
        "/api/connection/test",
        json={
            "base_url": "http://localhost:8000/v1",
            "model": "local-llm",
            "adapter": "auto",
            "api_key": "sk-test",
        },
    )
    assert r.status_code == 200
    assert r.json()["effective_base_url"] is None
