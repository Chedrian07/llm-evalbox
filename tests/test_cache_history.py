# SPDX-License-Identifier: Apache-2.0
"""Persistent SQLite run-history."""

from __future__ import annotations

import pytest

from llm_evalbox.cache import (
    clear_runs,
    delete_run,
    get_run,
    list_runs,
    upsert_run,
)


@pytest.fixture(autouse=True)
def _isolated_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("EVALBOX_CACHE_DIR", str(tmp_path))


def _payload(run_id: str, model: str, acc: float = 0.85, cost: float | None = 0.01):
    return {
        "schema_version": 1,
        "run_id": run_id,
        "started_at": "2026-05-03T00:00:00Z",
        "finished_at": "2026-05-03T00:01:00Z",
        "provider": {"adapter": "chat_completions",
                     "base_url": "https://api.test/v1",
                     "model": model},
        "thinking": {"mode": "off", "used": False},
        "benchmarks": [
            {"name": "mmlu", "samples": 10, "accuracy": acc,
             "tokens": {"prompt": 1, "completion": 1, "reasoning": 0, "cached_prompt": 0},
             "cost_usd_estimated": cost, "duration_s": 1, "thinking_used": False,
             "denominator_policy": "lenient", "category_scores": {},
             "error_breakdown": {"ok": 10}, "latency_ms": {"p50": 100, "p95": 200},
             "accuracy_ci95": [0.6, 0.95], "cache_hits": 0},
        ],
        "totals": {
            "accuracy_macro": acc,
            "tokens": {"prompt": 1, "completion": 1, "reasoning": 0, "cached_prompt": 0},
            "cost_usd_estimated": cost,
        },
        "messages": [
            {
                "role": "system",
                "content": "run started",
                "created_at": "2026-05-03T00:00:00Z",
                "metadata": {"type": "status", "phase": "started"},
            },
        ],
    }


def test_upsert_and_list():
    upsert_run(_payload("evalbox-a", "model-x", 0.7))
    upsert_run(_payload("evalbox-b", "model-y", 0.9))
    rows = list_runs()
    ids = {r["run_id"] for r in rows}
    assert ids == {"evalbox-a", "evalbox-b"}


def test_upsert_idempotent():
    upsert_run(_payload("evalbox-a", "model-x", 0.5))
    upsert_run(_payload("evalbox-a", "model-x", 0.9))  # update
    rows = list_runs()
    assert len(rows) == 1
    assert rows[0]["accuracy_macro"] == pytest.approx(0.9)


def test_get_run_returns_full_payload():
    upsert_run(_payload("evalbox-a", "model-x"))
    payload = get_run("evalbox-a")
    assert payload is not None
    assert payload["run_id"] == "evalbox-a"
    assert payload["benchmarks"][0]["accuracy"] == pytest.approx(0.85)
    assert payload["messages"][0]["content"] == "run started"


def test_get_run_unknown():
    assert get_run("does-not-exist") is None


def test_filter_by_model():
    upsert_run(_payload("evalbox-a", "model-x"))
    upsert_run(_payload("evalbox-b", "model-y"))
    rows = list_runs(model="model-x")
    assert {r["run_id"] for r in rows} == {"evalbox-a"}


def test_delete_run():
    upsert_run(_payload("evalbox-a", "model-x"))
    assert delete_run("evalbox-a") is True
    assert delete_run("evalbox-a") is False
    assert list_runs() == []


def test_clear_runs():
    upsert_run(_payload("evalbox-a", "model-x"))
    upsert_run(_payload("evalbox-b", "model-y"))
    n = clear_runs()
    assert n == 2
    assert list_runs() == []


def test_payload_without_run_id_is_silently_skipped():
    upsert_run({"no_run_id": True})
    assert list_runs() == []


def test_history_via_web(monkeypatch, tmp_path):
    monkeypatch.setenv("EVALBOX_CACHE_DIR", str(tmp_path))
    from fastapi.testclient import TestClient

    from llm_evalbox.web.server import build_app
    upsert_run(_payload("evalbox-a", "model-x", 0.7))
    upsert_run(_payload("evalbox-b", "model-y", 0.9))
    c = TestClient(build_app())
    rows = c.get("/api/history").json()
    assert {r["run_id"] for r in rows} == {"evalbox-a", "evalbox-b"}
    detail = c.get("/api/history/evalbox-a").json()
    assert detail["run_id"] == "evalbox-a"
    r = c.delete("/api/history/evalbox-a")
    assert r.status_code == 200
    assert c.get("/api/history/evalbox-a").status_code == 404
