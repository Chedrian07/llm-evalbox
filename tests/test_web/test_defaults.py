# SPDX-License-Identifier: Apache-2.0
"""GET /api/defaults — surface env/.env values without leaking secrets."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from llm_evalbox.web.server import build_app


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    # Wipe anything the host environment might have set so the test sees a
    # clean baseline. Individual tests opt into specific values.
    for name in (
        "EVALBOX_BASE_URL", "EVALBOX_MODEL", "EVALBOX_ADAPTER", "EVALBOX_PROFILE",
        "EVALBOX_THINKING", "EVALBOX_REASONING_EFFORT",
        "EVALBOX_CONCURRENCY", "EVALBOX_RPM", "EVALBOX_TPM",
        "EVALBOX_MAX_COST_USD", "EVALBOX_ACCEPT_CODE_EXEC", "EVALBOX_NO_CACHE",
        "EVALBOX_STRICT_FAILURES", "EVALBOX_NO_THINKING_RERUN",
        "EVALBOX_PROMPT_CACHE_AWARE", "EVALBOX_DROP_PARAMS",
        "OPENAI_API_KEY", "OPENROUTER_API_KEY", "TOGETHER_API_KEY",
        "FIREWORKS_API_KEY", "VLLM_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
        "E2B_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def client():
    return TestClient(build_app())


def test_defaults_empty_env(client):
    r = client.get("/api/defaults")
    assert r.status_code == 200
    body = r.json()
    assert body["base_url"] is None
    assert body["model"] is None
    assert body["api_key_env"] == "OPENAI_API_KEY"
    assert body["has_api_key"] is False
    assert body["detected_api_key_envs"] == []
    # Every candidate is reported, all False.
    assert body["api_keys"]["OPENAI_API_KEY"] is False
    assert body["api_keys"]["OPENROUTER_API_KEY"] is False
    # Boolean toggles default to False.
    assert body["accept_code_exec"] is False
    assert body["no_cache"] is False
    assert body["strict_failures"] is False
    assert body["no_thinking_rerun"] is False
    assert body["prompt_cache_aware"] is False


def test_defaults_picks_up_evalbox_env(client, monkeypatch):
    monkeypatch.setenv("EVALBOX_BASE_URL", "https://api.test/v1")
    monkeypatch.setenv("EVALBOX_MODEL", "gpt-5.4-mini")
    monkeypatch.setenv("EVALBOX_ADAPTER", "chat_completions")
    monkeypatch.setenv("EVALBOX_THINKING", "on")
    monkeypatch.setenv("EVALBOX_CONCURRENCY", "16")
    monkeypatch.setenv("EVALBOX_MAX_COST_USD", "10.5")
    monkeypatch.setenv("EVALBOX_ACCEPT_CODE_EXEC", "1")
    body = client.get("/api/defaults").json()
    assert body["base_url"] == "https://api.test/v1"
    assert body["model"] == "gpt-5.4-mini"
    assert body["adapter"] == "chat_completions"
    assert body["thinking"] == "on"
    assert body["concurrency"] == 16
    assert body["max_cost_usd"] == 10.5
    assert body["accept_code_exec"] is True


def test_defaults_picks_up_extended_toggles(client, monkeypatch):
    monkeypatch.setenv("EVALBOX_REASONING_EFFORT", "high")
    monkeypatch.setenv("EVALBOX_STRICT_FAILURES", "1")
    monkeypatch.setenv("EVALBOX_NO_THINKING_RERUN", "true")
    monkeypatch.setenv("EVALBOX_PROMPT_CACHE_AWARE", "yes")
    monkeypatch.setenv("EVALBOX_NO_CACHE", "on")
    monkeypatch.setenv("EVALBOX_PROFILE", "openrouter")
    body = client.get("/api/defaults").json()
    assert body["reasoning_effort"] == "high"
    assert body["strict_failures"] is True
    assert body["no_thinking_rerun"] is True
    assert body["prompt_cache_aware"] is True
    assert body["no_cache"] is True
    assert body["profile"] == "openrouter"


def test_defaults_strips_whitespace_only_values(client, monkeypatch):
    # Whitespace-only env vars are common typos and would otherwise poison
    # SPA inputs ("   " becomes the model name, etc.).
    monkeypatch.setenv("EVALBOX_BASE_URL", "   ")
    monkeypatch.setenv("EVALBOX_MODEL", "\t\n")
    monkeypatch.setenv("EVALBOX_CONCURRENCY", " 12 ")
    body = client.get("/api/defaults").json()
    assert body["base_url"] is None
    assert body["model"] is None
    assert body["concurrency"] == 12


def test_defaults_reports_api_key_presence_without_value(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-totally-secret-please-do-not-leak")
    body = client.get("/api/defaults").json()
    assert body["has_api_key"] is True
    assert body["api_key_env"] == "OPENAI_API_KEY"
    assert "OPENAI_API_KEY" in body["detected_api_key_envs"]
    assert body["api_keys"]["OPENAI_API_KEY"] is True
    # The value itself must not appear anywhere in the response.
    raw = client.get("/api/defaults").text
    assert "sk-totally-secret-please-do-not-leak" not in raw


def test_defaults_detects_multiple_api_key_envs(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-1")
    monkeypatch.setenv("TOGETHER_API_KEY", "sk-tg-1")
    body = client.get("/api/defaults").json()
    assert body["has_api_key"] is True
    assert "OPENROUTER_API_KEY" in body["detected_api_key_envs"]
    assert "TOGETHER_API_KEY" in body["detected_api_key_envs"]
    # api_keys should report the present keys true and the rest false.
    assert body["api_keys"]["OPENROUTER_API_KEY"] is True
    assert body["api_keys"]["TOGETHER_API_KEY"] is True
    assert body["api_keys"]["OPENAI_API_KEY"] is False


def test_defaults_handles_invalid_int_gracefully(client, monkeypatch):
    monkeypatch.setenv("EVALBOX_CONCURRENCY", "not-a-number")
    body = client.get("/api/defaults").json()
    assert body["concurrency"] is None
