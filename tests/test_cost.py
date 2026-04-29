# SPDX-License-Identifier: Apache-2.0
import pytest

from llm_evalbox.core.request import Usage
from llm_evalbox.pricing import PriceOverrides, cost_for_usage, lookup_price


def test_lookup_price_known_model():
    p = lookup_price("gpt-4o-mini")
    assert p is not None
    assert p.input == pytest.approx(0.15)
    assert p.output == pytest.approx(0.60)


def test_lookup_unknown_returns_none():
    assert lookup_price("totally-imaginary-model-xyz") is None


def test_cost_for_usage_simple():
    u = Usage(prompt_tokens=1_000_000, completion_tokens=1_000_000, total_tokens=2_000_000)
    cost = cost_for_usage("gpt-4o-mini", u)
    # 1M prompt @ 0.15 + 1M output @ 0.60 = 0.75
    assert cost == pytest.approx(0.75, rel=1e-3)


def test_cost_overrides_take_precedence():
    u = Usage(prompt_tokens=1_000_000, completion_tokens=0, total_tokens=1_000_000)
    cost = cost_for_usage(
        "totally-imaginary-model-xyz",
        u,
        overrides=PriceOverrides(input=2.0, output=0.0),
    )
    assert cost == pytest.approx(2.0, rel=1e-3)


def test_cost_with_cached_and_reasoning_tokens():
    u = Usage(
        prompt_tokens=1_000_000,
        cached_prompt_tokens=500_000,
        completion_tokens=1_000_000,
        reasoning_tokens=400_000,
        total_tokens=2_000_000,
    )
    cost = cost_for_usage("gpt-4o-mini", u)
    # uncached prompt 0.5M @ 0.15 + cached 0.5M @ 0.075 + completion(non-reasoning) 0.6M @ 0.60 + reasoning 0.4M @ 0.60
    expected = (0.5 * 0.15 + 0.5 * 0.075 + 0.6 * 0.60 + 0.4 * 0.60)
    assert cost == pytest.approx(expected, rel=1e-3)


def test_cost_unknown_model_no_overrides_returns_none():
    u = Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20)
    assert cost_for_usage("unknown-XXX-model", u) is None
