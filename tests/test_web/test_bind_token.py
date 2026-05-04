# SPDX-License-Identifier: Apache-2.0
"""Bind-token middleware — header, cookie, and SPA-shell auto-seeding."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from llm_evalbox.web.server import build_app


@pytest.fixture
def secured_client():
    """An app instance with a known bind-token."""
    app = build_app(bind_token="secret-token-32hex")
    return TestClient(app)


def test_api_blocked_without_token(secured_client):
    r = secured_client.get("/api/benchmarks")
    assert r.status_code == 401
    assert "missing or bad" in r.json()["detail"]


def test_health_is_public_for_container_healthcheck(secured_client):
    r = secured_client.get("/api/health")
    assert r.status_code == 200


def test_api_passes_with_header(secured_client):
    r = secured_client.get("/api/benchmarks", headers={"X-Evalbox-Token": "secret-token-32hex"})
    assert r.status_code == 200


def test_api_passes_with_cookie(secured_client):
    secured_client.cookies.set("evalbox_token", "secret-token-32hex")
    r = secured_client.get("/api/benchmarks")
    assert r.status_code == 200


def test_spa_shell_does_not_seed_cookie_without_bootstrap(secured_client):
    r = secured_client.get("/")
    assert r.status_code == 200
    assert "evalbox_token" not in r.cookies
    assert secured_client.get("/api/benchmarks").status_code == 401


def test_spa_shell_bootstrap_query_seeds_cookie(secured_client):
    """The user opens the printed bootstrap URL once, then same-origin
    fetch() and EventSource requests carry the HttpOnly cookie automatically."""
    r = secured_client.get("/?evalbox_token=secret-token-32hex")
    assert r.history
    r = secured_client.get("/")
    assert r.status_code == 200
    assert secured_client.cookies.get("evalbox_token") == "secret-token-32hex"
    assert secured_client.get("/api/benchmarks").status_code == 200


def test_no_token_means_no_middleware():
    """When bind_token is None (loopback bind, no security), the
    middleware is never installed — health works without any header."""
    app = build_app(bind_token=None)
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
