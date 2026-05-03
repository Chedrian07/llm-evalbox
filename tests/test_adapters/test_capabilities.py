# SPDX-License-Identifier: Apache-2.0

import pytest

from llm_evalbox.adapters.capabilities import (
    capability_for,
    strip_unsupported_keys,
)


def test_o_series_strips_temperature():
    cap = capability_for("o1-mini")
    assert cap.accepts_temperature is False
    assert cap.accepts_reasoning_effort is True
    assert cap.use_max_completion_tokens is True


def test_qwen3_accepts_top_k():
    cap = capability_for("Qwen/Qwen3-32B")
    assert cap.accepts_top_k is True


def test_default_no_top_k():
    cap = capability_for("gpt-4o")
    assert cap.accepts_top_k is False


def test_strip_removes_top_k_for_default_model():
    cap = capability_for("gpt-4o-mini")
    body = {"model": "gpt-4o-mini", "temperature": 0.0, "top_k": 20, "stop": ["X"]}
    out = strip_unsupported_keys(body, cap)
    assert "top_k" not in out
    assert "temperature" in out
    assert "stop" in out


def test_user_drop_params_force_strip():
    cap = capability_for("Qwen/Qwen3-32B")  # accepts top_k
    body = {"top_k": 20, "stop": ["X"]}
    out = strip_unsupported_keys(body, cap, user_drop=["top_k"])
    assert "top_k" not in out
    assert "stop" in out


@pytest.mark.parametrize("message,expected", [
    # Variations we've seen in the wild
    ("HTTP 400: unrecognized parameter: top_k", {"top_k"}),
    ("Error: 'reasoning_effort' is not supported by this model", {"reasoning_effort"}),
    ("unknown argument: presence_penalty", {"presence_penalty"}),
    ("invalid value for 'temperature' must be between 0 and 1", {"temperature"}),
    ('parameter "frequency_penalty" is not supported', {"frequency_penalty"}),
    # gpt-5.4-mini specific: maps the value back to reasoning_effort
    ("level \"minimal\" not supported, valid levels: low, medium, high, xhigh",
     {"reasoning_effort"}),
    # multiple in one message
    ("unrecognized parameter: top_k. unknown key: stop", {"top_k", "stop"}),
    # nothing to extract
    ("server overloaded, please retry", set()),
    # extracted but not a known sampling key → filtered out
    ("unknown argument: frobnicate", set()),
])
def test_parse_unsupported_param_error(message, expected):
    from llm_evalbox.adapters.capabilities import parse_unsupported_param_error
    assert parse_unsupported_param_error(message) == expected


def test_temperature_floor_clamped():
    cap = capability_for("o3-mini")  # max_temperature_floor=1.0
    body = {"temperature": 0.0}
    out = strip_unsupported_keys(body, cap)
    # accepts_temperature=False on o-series → key gets stripped entirely
    assert "temperature" not in out
