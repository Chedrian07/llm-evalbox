# SPDX-License-Identifier: Apache-2.0

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


def test_temperature_floor_clamped():
    cap = capability_for("o3-mini")  # max_temperature_floor=1.0
    body = {"temperature": 0.0}
    out = strip_unsupported_keys(body, cap)
    # accepts_temperature=False on o-series → key gets stripped entirely
    assert "temperature" not in out
