# SPDX-License-Identifier: Apache-2.0
"""Markdown / HTML / compare exporters: shape and presence."""

from __future__ import annotations

from llm_evalbox.reports import (
    render_compare_md,
    render_run_html,
    render_run_md,
)


def _payload(model: str = "fake-model", acc: float = 0.85) -> dict:
    return {
        "schema_version": 1,
        "run_id": f"evalbox-test-{model}",
        "started_at": "2026-05-03T00:00:00Z",
        "finished_at": "2026-05-03T00:01:00Z",
        "seed": 42,
        "provider": {"adapter": "chat_completions",
                     "base_url": "https://api.test/v1",
                     "model": model},
        "thinking": {"mode": "off", "used": False},
        "capability": {"accepts_temperature": True, "accepts_top_k": False,
                       "accepts_seed": True, "accepts_reasoning_effort": False},
        "strict_deterministic": False,
        "strict_failures": False,
        "benchmarks": [
            {
                "name": "mmlu", "samples": 30,
                "accuracy": acc, "accuracy_ci95": [0.7, 0.95],
                "category_scores": {"abstract_algebra": 1.0},
                "error_breakdown": {"ok": 26, "wrong_answer": 4},
                "latency_ms": {"p50": 1234, "p95": 4567},
                "tokens": {"prompt": 100000, "completion": 5000,
                           "reasoning": 0, "cached_prompt": 0,
                           "reasoning_estimated": False},
                "cost_usd_estimated": 0.0234,
                "duration_s": 60.0,
                "thinking_used": False,
                "denominator_policy": "lenient",
                "cache_hits": 0,
            }
        ],
        "totals": {
            "accuracy_macro": acc,
            "tokens": {"prompt": 100000, "completion": 5000,
                       "reasoning": 0, "cached_prompt": 0},
            "cost_usd_estimated": 0.0234,
        },
    }


def test_render_run_md_includes_key_fields():
    p = _payload("gpt-4o-mini", 0.85)
    md = render_run_md(p)
    assert "gpt-4o-mini" in md
    assert "mmlu" in md
    assert "0.8500" in md
    assert "$0.0234" in md
    # Markdown table header present
    assert "| benchmark | samples | accuracy" in md


def test_render_run_html_is_self_contained():
    p = _payload("o3-mini", 0.9)
    s = render_run_html(p)
    assert s.startswith("<!doctype html>")
    assert "</html>" in s.lower()
    # No external assets
    assert "<link" not in s.lower()
    assert "<script src=" not in s.lower()
    # Key data present
    assert "o3-mini" in s
    assert "0.9000" in s


def test_render_compare_md_lists_each_model_column():
    a = _payload("model-a", 0.7)
    b = _payload("model-b", 0.85)
    md = render_compare_md([a, b])
    assert "| benchmark" in md
    assert "model-a" in md
    assert "model-b" in md
    # Cell shows acc + cost
    assert "0.7000" in md and "0.8500" in md
