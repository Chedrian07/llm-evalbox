# SPDX-License-Identifier: Apache-2.0
"""Unit tests for `rewrite_localhost`."""

from __future__ import annotations

import pytest

from llm_evalbox.adapters.url_rewrite import (
    CONTAINER_HOST,
    in_container,
    rewrite_localhost,
)


@pytest.mark.parametrize(
    "url,expected",
    [
        ("http://localhost:8000/v1", f"http://{CONTAINER_HOST}:8000/v1"),
        ("http://127.0.0.1:11434/v1", f"http://{CONTAINER_HOST}:11434/v1"),
        ("http://[::1]:8080/v1", f"http://{CONTAINER_HOST}:8080/v1"),
        ("http://0.0.0.0:8000/v1", f"http://{CONTAINER_HOST}:8000/v1"),
    ],
)
def test_rewrites_loopback_hosts_in_container(url, expected):
    out, did = rewrite_localhost(url, in_container_=True, mode="auto")
    assert did is True
    assert out == expected


def test_unchanged_for_public_url():
    url = "https://api.openai.com/v1"
    out, did = rewrite_localhost(url, in_container_=True, mode="auto")
    assert did is False
    assert out == url


def test_unchanged_for_lan_ip():
    url = "http://192.168.1.50:8000/v1"
    out, did = rewrite_localhost(url, in_container_=True, mode="auto")
    assert did is False
    assert out == url


def test_preserves_path_and_query():
    url = "https://localhost:8000/v1/chat/completions?stream=true"
    out, did = rewrite_localhost(url, in_container_=True, mode="auto")
    assert did is True
    assert out == f"https://{CONTAINER_HOST}:8000/v1/chat/completions?stream=true"


def test_preserves_userinfo():
    url = "http://user:pw@localhost:8000/v1"
    out, did = rewrite_localhost(url, in_container_=True, mode="auto")
    assert did is True
    assert out == f"http://user:pw@{CONTAINER_HOST}:8000/v1"


def test_no_rewrite_outside_container_in_auto():
    out, did = rewrite_localhost(
        "http://localhost:8000/v1", in_container_=False, mode="auto"
    )
    assert did is False
    assert out == "http://localhost:8000/v1"


def test_mode_on_forces_rewrite_outside_container():
    out, did = rewrite_localhost(
        "http://localhost:8000/v1", in_container_=False, mode="on"
    )
    assert did is True
    assert out == f"http://{CONTAINER_HOST}:8000/v1"


def test_mode_off_kill_switch():
    out, did = rewrite_localhost(
        "http://localhost:8000/v1", in_container_=True, mode="off"
    )
    assert did is False
    assert out == "http://localhost:8000/v1"


def test_empty_url():
    out, did = rewrite_localhost("", in_container_=True, mode="auto")
    assert did is False
    assert out == ""


def test_garbled_url_passes_through():
    # `urlsplit` is tolerant — invalid schemes still parse but yield no
    # hostname, so we should leave them alone.
    out, did = rewrite_localhost("not a url", in_container_=True, mode="auto")
    assert did is False
    assert out == "not a url"


def test_env_localhost_rewrite_off(monkeypatch):
    monkeypatch.setenv("EVALBOX_LOCALHOST_REWRITE", "off")
    out, did = rewrite_localhost("http://localhost:8000/v1", in_container_=True)
    assert did is False
    assert out == "http://localhost:8000/v1"


def test_env_localhost_rewrite_on(monkeypatch):
    monkeypatch.setenv("EVALBOX_LOCALHOST_REWRITE", "on")
    out, did = rewrite_localhost("http://localhost:8000/v1", in_container_=False)
    assert did is True
    assert out == f"http://{CONTAINER_HOST}:8000/v1"


def test_in_container_env_marker(monkeypatch):
    monkeypatch.setenv("EVALBOX_IN_DOCKER", "1")
    assert in_container() is True


def test_case_insensitive_localhost(monkeypatch):
    out, did = rewrite_localhost("http://LOCALHOST:8000", in_container_=True, mode="auto")
    assert did is True
    assert out == f"http://{CONTAINER_HOST}:8000"
