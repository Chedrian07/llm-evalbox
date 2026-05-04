# SPDX-License-Identifier: Apache-2.0
"""/api/profiles CRUD round-trip."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from llm_evalbox.web.server import build_app


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("EVALBOX_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("EVALBOX_CACHE_DIR", raising=False)
    monkeypatch.delenv("EVALBOX_CONFIG_DIR", raising=False)


@pytest.fixture
def client():
    return TestClient(build_app())


def test_post_then_get(client):
    payload = {
        "name": "openai-public",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "adapter": "auto",
        "api_key_env": "OPENAI_API_KEY",
        "extra_headers": {"X-Foo": "bar"},
        "sampling": {"temperature": 0.0},
    }
    r = client.post("/api/profiles", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "openai-public"
    assert body["sampling"] == {"temperature": 0.0}

    listed = client.get("/api/profiles").json()
    assert any(p["name"] == "openai-public" for p in listed)

    one = client.get("/api/profiles/openai-public").json()
    assert one["base_url"] == "https://api.openai.com/v1"


def test_404_on_missing(client):
    r = client.get("/api/profiles/nope")
    assert r.status_code == 404
    r = client.delete("/api/profiles/nope")
    assert r.status_code == 404
    r = client.post("/api/profiles/nope/use")
    assert r.status_code == 404


def test_use_bumps_recency(client):
    client.post("/api/profiles", json={"name": "a", "base_url": "http://a"})
    client.post("/api/profiles", json={"name": "b", "base_url": "http://b"})
    # 'b' was created last; without `use` it sorts first.
    listed = client.get("/api/profiles").json()
    assert listed[0]["name"] == "b"
    # `use` on 'a' bumps it to the front.
    client.post("/api/profiles/a/use")
    listed = client.get("/api/profiles").json()
    assert listed[0]["name"] == "a"


def test_empty_name_rejected(client):
    r = client.post("/api/profiles", json={"name": "", "base_url": "http://a"})
    # Pydantic min_length=1 → 422 (validation error), our ValueError is unreachable here.
    assert r.status_code == 422


def test_delete_round_trip(client):
    client.post("/api/profiles", json={"name": "tmp", "base_url": "http://x"})
    r = client.delete("/api/profiles/tmp")
    assert r.status_code == 200
    assert r.json() == {"deleted": True}
    assert client.get("/api/profiles/tmp").status_code == 404
