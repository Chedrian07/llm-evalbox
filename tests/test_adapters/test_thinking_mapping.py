# SPDX-License-Identifier: Apache-2.0
"""Thinking matrix: encoding sites + auto-detection parsing."""

from __future__ import annotations

import pytest

from llm_evalbox.core.thinking import (
    apply_thinking_to_request,
    detect_family,
    parse_thinking,
    thinking_token_budget,
)


@pytest.mark.parametrize("model,family", [
    ("Qwen/Qwen3-32B", "qwen3"),
    ("zhipu/glm-4.5-air", "glm-4.5+"),
    ("deepseek-r1-distill", "deepseek-r1"),
    ("o1-mini", "openai-o-series"),
    ("gpt-5-thinking", "gpt-5"),
    ("gpt-oss-20b", "gpt-oss"),
    ("anthropic/claude-3.5-sonnet", "anthropic"),
    ("google/gemini-1.5-pro", "gemini"),
    ("totally-unknown", None),
])
def test_detect_family(model, family):
    f = detect_family(model)
    if family is None:
        assert f is None
    else:
        assert f is not None and f.family == family


def test_apply_thinking_qwen3_on():
    ct, re_eff, ex, warns = apply_thinking_to_request(
        model="Qwen/Qwen3-32B",
        mode="on",
        chat_template_kwargs={},
        reasoning_effort=None,
        extra={},
    )
    assert ct["enable_thinking"] is True
    assert re_eff is None
    assert ex == {}


def test_apply_thinking_o_series_off_default_low():
    """off → 'low' (cross-vendor safe; some gpt-5 variants reject 'minimal')."""
    ct, re_eff, ex, warns = apply_thinking_to_request(
        model="o3-mini",
        mode="off",
        chat_template_kwargs={},
        reasoning_effort=None,
        extra={},
    )
    assert re_eff == "low"


def test_apply_thinking_explicit_effort_preserved():
    """User-specified reasoning_effort is never overwritten."""
    ct, re_eff, ex, warns = apply_thinking_to_request(
        model="gpt-5",
        mode="off",
        chat_template_kwargs={},
        reasoning_effort="minimal",  # user opted into minimal explicitly
        extra={},
    )
    assert re_eff == "minimal"


def test_apply_thinking_o_series_on_default_high():
    ct, re_eff, ex, warns = apply_thinking_to_request(
        model="o3-mini",
        mode="on",
        chat_template_kwargs={},
        reasoning_effort=None,
        extra={},
    )
    assert re_eff == "high"


def test_apply_thinking_anthropic_on_extended_thinking():
    ct, re_eff, ex, warns = apply_thinking_to_request(
        model="anthropic/claude-3.5-sonnet",
        mode="on",
        chat_template_kwargs={},
        reasoning_effort=None,
        extra={},
    )
    et = ex.get("extended_thinking")
    assert et and et["enabled"] is True and et["budget_tokens"] >= 1


def test_apply_thinking_gemini_on_minus1():
    ct, re_eff, ex, warns = apply_thinking_to_request(
        model="gemini-1.5-flash",
        mode="on",
        chat_template_kwargs={},
        reasoning_effort=None,
        extra={},
    )
    assert ex["thinking_config"]["thinking_budget"] == -1


def test_apply_thinking_deepseek_off_warns():
    ct, re_eff, ex, warns = apply_thinking_to_request(
        model="deepseek-r1",
        mode="off",
        chat_template_kwargs={},
        reasoning_effort=None,
        extra={},
    )
    assert any("non-toggleable" in w for w in warns)


def test_apply_thinking_auto_is_noop():
    ct, re_eff, ex, warns = apply_thinking_to_request(
        model="Qwen/Qwen3-32B",
        mode="auto",
        chat_template_kwargs={"enable_thinking": False},  # caller's existing setting preserved
        reasoning_effort=None,
        extra={},
    )
    assert ct == {"enable_thinking": False}


def test_token_budget_clamp():
    assert thinking_token_budget(base_max_tokens=128, model="Qwen3-32B", thinking_on=True) >= 8192
    assert thinking_token_budget(base_max_tokens=128, model="Qwen3-32B", thinking_on=False) == 128


def test_token_budget_gpt_oss_quadruples():
    assert thinking_token_budget(base_max_tokens=4000, model="gpt-oss-20b", thinking_on=True) == 16000


def test_parse_thinking_strips_think_tag():
    visible, reasoning, observed = parse_thinking("<think>secret</think>visible answer")
    assert visible == "visible answer"
    assert reasoning == "secret"
    assert observed is True


def test_parse_thinking_no_tag():
    visible, reasoning, observed = parse_thinking("just text", {})
    assert visible == "just text"
    assert reasoning == ""
    assert observed is False


def test_parse_thinking_reasoning_content_field():
    raw = {"choices": [{"message": {"reasoning_content": "behind the scenes"}}]}
    visible, reasoning, observed = parse_thinking("answer", raw)
    assert observed is True
    assert "behind the scenes" in reasoning
