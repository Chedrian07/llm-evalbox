# SPDX-License-Identifier: Apache-2.0
"""PATCH /api/history/{run_id} round-trip + filter query."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from llm_evalbox.cache import upsert_run
from llm_evalbox.web.server import build_app


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("EVALBOX_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("EVALBOX_CACHE_DIR", raising=False)
    monkeypatch.delenv("EVALBOX_CONFIG_DIR", raising=False)


@pytest.fixture
def client():
    return TestClient(build_app())


def _seed(run_id: str, model: str = "gpt-x") -> None:
    upsert_run({
        "run_id": run_id,
        "started_at": "2026-05-04T00:00:00Z",
        "finished_at": "2026-05-04T00:01:00Z",
        "provider": {"model": model, "base_url": "https://x", "adapter": "auto"},
        "totals": {"accuracy_macro": 0.8, "cost_usd_estimated": 0.01},
        "benchmarks": [{"name": "mmlu"}],
    })


def test_patch_starred_then_get_in_filter(client):
    _seed("r1")
    r = client.patch("/api/history/r1", json={"starred": True})
    assert r.status_code == 200
    assert r.json() == {"updated": True}

    rows = client.get("/api/history?starred=true").json()
    assert {row["run_id"] for row in rows} == {"r1"}


def test_patch_tags_and_notes_persist(client):
    _seed("r1")
    client.patch("/api/history/r1", json={
        "tags": ["fast", "vision"],
        "notes": "initial sweep",
    })
    rows = client.get("/api/history").json()
    assert rows[0]["tags"] == ["fast", "vision"]
    assert rows[0]["notes"] == "initial sweep"


def test_patch_404_when_run_missing(client):
    r = client.patch("/api/history/missing", json={"starred": True})
    assert r.status_code == 404


def test_filter_by_tag(client):
    _seed("r1")
    _seed("r2")
    client.patch("/api/history/r1", json={"tags": ["fast"]})
    rows = client.get("/api/history?tag=fast").json()
    assert {row["run_id"] for row in rows} == {"r1"}
