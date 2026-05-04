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
    # follow_redirects=False so we see Set-Cookie on the SPA fallback
    # response without it being swallowed by an intermediate redirect.
    return TestClient(app)


def test_api_blocked_without_token(secured_client):
    r = secured_client.get("/api/health")
    assert r.status_code == 401
    assert "missing or bad" in r.json()["detail"]


def test_api_passes_with_header(secured_client):
    r = secured_client.get("/api/health", headers={"X-Evalbox-Token": "secret-token-32hex"})
    assert r.status_code == 200


def test_api_passes_with_cookie(secured_client):
    secured_client.cookies.set("evalbox_token", "secret-token-32hex")
    r = secured_client.get("/api/health")
    assert r.status_code == 200


def test_spa_shell_seeds_cookie(secured_client):
    """`GET /` (SPA HTML or placeholder) sets the cookie so the browser
    gets it on first paint and every subsequent fetch() carries it."""
    r = secured_client.get("/")
    # 200 from either StaticFiles SPA or the placeholder route.
    assert r.status_code == 200
    assert "evalbox_token" in r.cookies
    assert r.cookies["evalbox_token"] == "secret-token-32hex"


def test_no_token_means_no_middleware():
    """When bind_token is None (loopback bind, no security), the
    middleware is never installed — health works without any header."""
    app = build_app(bind_token=None)
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
