# SPDX-License-Identifier: Apache-2.0
"""Smoke tests for the 9 newly-added benchmarks.

For each, we verify:
  - load_dataset returns >0 items (data is bundled).
  - sample item has the expected shape (`answer` is a single letter).
  - format_prompt renders.
  - extract_answer + check_answer roundtrip on a synthetic correct response.
"""

from __future__ import annotations

import pytest

from llm_evalbox.eval import get_benchmark
from llm_evalbox.eval._mc_common import normalize_answer
from llm_evalbox.eval._sandbox import accept_code_exec


@pytest.fixture(autouse=True)
def _accept_codeexec():
    accept_code_exec()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,n_choices_min",
    [
        ("mmlu_pro", 2),
        ("arc_challenge", 4),
        ("winogrande", 2),
        ("mathqa", 2),
        ("kmmlu", 4),
        ("cmmlu", 4),
        ("jmmlu", 4),
        ("bbq", 2),
        ("safetybench", 2),
    ],
)
async def test_bench_loads_and_scores(name, n_choices_min):
    bench = get_benchmark(name)
    items = await bench.load_dataset(3)
    assert len(items) >= 1, f"{name}: expected >0 items"

    item = items[0]
    # Either "choices" (most) or sentence+option1/2 (winogrande)
    nchoices = len(item.get("choices") or [])
    assert nchoices >= n_choices_min, f"{name}: only {nchoices} choices"

    # answer is a single letter A-J
    assert item["answer"] in "ABCDEFGHIJ", f"{name}: bad answer {item['answer']!r}"

    # format_prompt renders without error
    msgs = bench.format_prompt(item)
    assert len(msgs) >= 1
    assert msgs[-1].content  # non-empty

    # Extract+check roundtrip: a response that says "Answer: X" where X is gold
    fake_response = f"After thinking, the answer is {item['answer']}."
    predicted = bench.extract_answer(fake_response, item)
    assert predicted == item["answer"]
    assert bench.check_answer(predicted, item) is True


def test_normalize_answer_letter():
    assert normalize_answer("B", ["a", "b", "c"]) == "B"
    assert normalize_answer("b", ["a", "b", "c"]) == "B"


def test_normalize_answer_int_zero_indexed():
    assert normalize_answer(0, ["a", "b", "c"]) == "A"
    assert normalize_answer(2, ["a", "b", "c"]) == "C"
    assert normalize_answer(5, ["a", "b", "c"]) == ""  # out of range


def test_normalize_answer_numeric_string():
    assert normalize_answer("0", ["a", "b", "c"]) == "A"
    assert normalize_answer("2", ["a", "b", "c"]) == "C"


def test_normalize_answer_invalid():
    assert normalize_answer(None, ["a", "b"]) == ""
    assert normalize_answer("zzz", ["a", "b"]) == ""


@pytest.mark.asyncio
async def test_kmmlu_one_indexed_correctly_shifted():
    """KMMLU stores 1..4; we shift to 0..3 before mapping to letters.
    A previous bug returned empty for ~30% of items (answer=4 → out of range)."""
    bench = get_benchmark("kmmlu")
    items = await bench.load_dataset(0)
    assert len(items) > 1000
    # No empty answers
    assert all(it["answer"] in "ABCDEFGHIJ" for it in items)


@pytest.mark.asyncio
async def test_winogrande_binary_letters():
    bench = get_benchmark("winogrande")
    items = await bench.load_dataset(50)
    assert len(items) >= 1
    for it in items:
        assert it["answer"] in ("A", "B")
        assert len(it["choices"]) == 2


@pytest.mark.asyncio
async def test_bbq_has_category():
    bench = get_benchmark("bbq")
    items = await bench.load_dataset(20)
    assert len(items) >= 1
    cats = {it.get("category") for it in items if it.get("category")}
    assert len(cats) >= 1, "BBQ items should carry a bias-axis category"
