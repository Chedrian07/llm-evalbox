# SPDX-License-Identifier: Apache-2.0
"""Persistent learned drop_params store."""

from __future__ import annotations

import pytest

from llm_evalbox.adapters import (
    clear_learned,
    forget_learned,
    list_learned,
    lookup_learned,
    remember_learned,
)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    # Redirect HOME so the json file lives under tmp.
    monkeypatch.setenv("HOME", str(tmp_path))


def test_remember_then_lookup():
    remember_learned("gpt-5.4-mini", ["reasoning_effort"])
    assert lookup_learned("gpt-5.4-mini") == ["reasoning_effort"]


def test_remember_unions():
    remember_learned("gpt-5.4-mini", ["reasoning_effort"])
    remember_learned("gpt-5.4-mini", ["top_k"])
    out = lookup_learned("gpt-5.4-mini")
    assert set(out) == {"reasoning_effort", "top_k"}


def test_lookup_substring_match():
    remember_learned("gpt-5", ["reasoning_effort"])
    # A more specific runtime model should still pick up the parent rule.
    assert lookup_learned("gpt-5.4-mini-2026-01-01") == ["reasoning_effort"]


def test_lookup_specific_overrides_substring():
    remember_learned("gpt-5", ["reasoning_effort"])
    remember_learned("gpt-5.4-mini", ["reasoning_effort", "top_k"])
    out = lookup_learned("gpt-5.4-mini")
    assert set(out) == {"reasoning_effort", "top_k"}


def test_list_learned_returns_all():
    remember_learned("a", ["x"])
    remember_learned("b", ["y"])
    rows = list_learned()
    assert {r["model"] for r in rows} == {"a", "b"}


def test_forget_and_clear():
    remember_learned("a", ["x"])
    remember_learned("b", ["y"])
    assert forget_learned("a") is True
    assert forget_learned("missing") is False
    assert {r["model"] for r in list_learned()} == {"b"}
    n = clear_learned()
    assert n == 1
    assert list_learned() == []


def test_remember_empty_is_noop():
    remember_learned("gpt-5", [])
    assert list_learned() == []
    remember_learned("", ["x"])
    assert list_learned() == []


def test_lookup_unknown_returns_empty():
    assert lookup_learned("does-not-exist") == []
