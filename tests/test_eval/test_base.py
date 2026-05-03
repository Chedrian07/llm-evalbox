# SPDX-License-Identifier: Apache-2.0
"""End-to-end run() with a deterministic mock adapter."""

from __future__ import annotations

import pytest

from llm_evalbox.adapters.base import ChatAdapter
from llm_evalbox.core.messages import Message
from llm_evalbox.core.request import ChatRequest, ChatResponse, ModelInfo, Usage
from llm_evalbox.eval.base import BaseBenchmark
from llm_evalbox.eval.extract import extract_mc_answer


class _MockAdapter(ChatAdapter):
    name = "mock"

    def __init__(self, answer_map: dict[str, str], think: bool = False):
        super().__init__()
        self._map = answer_map
        self._think = think

    async def chat(self, req: ChatRequest) -> ChatResponse:
        # Find which mini_mmlu item this prompt corresponds to (matches "Capital of France"):
        prompt = req.messages[-1].content
        # "answer key" in our test is the substring lookup
        for key, ans in self._map.items():
            if key in prompt:
                txt = f"<think>thinking…</think>\nThe answer is {ans}" if self._think else f"The answer is {ans}"
                return ChatResponse(
                    text=ans if not self._think else ans,
                    raw_text=txt,
                    finish_reason="stop",
                    usage=Usage(prompt_tokens=10, completion_tokens=1, total_tokens=11),
                    latency_ms=10.0,
                    thinking_observed=self._think,
                )
        return ChatResponse(text="?", raw_text="?", usage=Usage(prompt_tokens=5, completion_tokens=1, total_tokens=6))

    async def list_models(self) -> list[ModelInfo]:
        return []


class _MiniMC(BaseBenchmark):
    name = "mini_mc"

    async def load_dataset(self, sample_size: int = 0):
        return []  # provided by caller

    def format_prompt(self, item):
        return [Message(role="user", content=f"Q:{item['question']} ABCD")]

    def extract_answer(self, response, item):
        return extract_mc_answer(response, "ABCD")

    def check_answer(self, predicted, item):
        return predicted == item["answer"]


@pytest.mark.asyncio
async def test_run_perfect_accuracy(mini_mmlu):
    bench = _MiniMC()
    answer_map = {it["question"]: it["answer"] for it in mini_mmlu}
    adapter = _MockAdapter(answer_map)
    result = await bench.run(adapter, mini_mmlu, model="mock-model", concurrency=2, thinking="auto")
    assert result.samples == len(mini_mmlu)
    assert result.correct_count == len(mini_mmlu)
    assert result.accuracy == pytest.approx(1.0)
    assert result.thinking_used is False


@pytest.mark.asyncio
async def test_run_zero_accuracy(mini_mmlu):
    bench = _MiniMC()
    # Mock returns only "Z" so all wrong → "wrong_answer" classification
    adapter = _MockAdapter({"never": "Z"})
    result = await bench.run(adapter, mini_mmlu, model="mock-model", concurrency=2, thinking="off")
    assert result.accuracy == 0.0
    assert result.error_breakdown.get("wrong_answer", 0) + result.error_breakdown.get("ok", 0) >= 1


@pytest.mark.asyncio
async def test_run_auto_thinking_switch(mini_mmlu):
    bench = _MiniMC()
    # mock with think tags → should auto-switch to "on"
    answer_map = {it["question"]: it["answer"] for it in mini_mmlu}
    adapter = _MockAdapter(answer_map, think=True)
    result = await bench.run(
        adapter, mini_mmlu, model="mock-model", concurrency=2, thinking="auto"
    )
    assert result.thinking_used is True


@pytest.mark.asyncio
async def test_strict_failures_changes_denominator():
    """Sandbox/network failures should be excluded by default but counted in strict mode."""
    from llm_evalbox.adapters.base import ChatAdapter
    from llm_evalbox.core.exceptions import NetworkError

    class _PartiallyFailingAdapter(ChatAdapter):
        name = "fail-half"

        def __init__(self, fail_indices: set[int]):
            super().__init__()
            self._fail = fail_indices
            self._call = 0

        async def chat(self, req):
            i = self._call
            self._call += 1
            if i in self._fail:
                raise NetworkError("simulated timeout")
            from llm_evalbox.core.request import ChatResponse, Usage
            # Use the question text to look up the gold answer (same trick as _MockAdapter).
            # All answers are correct here.
            text = "B"  # mini_mmlu fixture has B for items 0,1,4
            return ChatResponse(
                text=text, raw_text=text,
                usage=Usage(prompt_tokens=10, completion_tokens=1, total_tokens=11),
                latency_ms=5.0,
            )

        async def list_models(self): return []

    items = [
        {"id": str(i), "question": f"q{i}", "choices": ["A","B","C","D"],
         "answer": "B", "subject": "x"}
        for i in range(4)
    ]

    bench = _MiniMC()

    # Lenient (default): 2 fail (network), 2 ok → 2/2 scored = 1.000
    adapter = _PartiallyFailingAdapter(fail_indices={0, 1})
    r = await bench.run(adapter, items, model="m", concurrency=4, thinking="off")
    assert r.error_breakdown.get("network") == 2
    assert r.error_breakdown.get("ok") == 2
    assert r.accuracy == pytest.approx(1.0)
    assert r.denominator_policy == "lenient"

    # Strict: 2 fail (network) + 2 ok → 2/4 = 0.500
    adapter2 = _PartiallyFailingAdapter(fail_indices={0, 1})
    r2 = await bench.run(adapter2, items, model="m", concurrency=4,
                         thinking="off", strict_failures=True)
    assert r2.accuracy == pytest.approx(0.5)
    assert r2.denominator_policy == "strict"


def test_wilson_ci_bounds():
    from llm_evalbox.eval.base import _wilson_ci
    lo, hi = _wilson_ci(50, 100)
    assert 0 <= lo <= 0.5 <= hi <= 1
    lo, hi = _wilson_ci(0, 0)
    assert (lo, hi) == (0.0, 0.0)


@pytest.mark.asyncio
async def test_runtime_adaptive_drop_params(monkeypatch, tmp_path):
    """Gateway returns 4xx for `seed` on the first call. After parsing it,
    the run should add `seed` to drop_params, retry, and succeed on every
    subsequent item without further 4xx — and not persist via the user's
    learned_capabilities.json (we redirect the path to tmp)."""
    # Redirect persistence so the test doesn't touch the user's real config.
    from llm_evalbox.adapters import learned as _learned
    from llm_evalbox.core.exceptions import BadRequestError
    monkeypatch.setattr(_learned, "store_path", lambda: tmp_path / "learned.json")

    class _SeedRejectingAdapter(ChatAdapter):
        name = "seed-rej"

        def __init__(self):
            super().__init__()
            self.calls = 0
            self.fail_calls = 0
            self.last_drop_params: list[list[str]] = []

        async def chat(self, req):
            self.calls += 1
            self.last_drop_params.append(list(req.drop_params))
            # Until "seed" is in drop_params, reject. After learning, succeed.
            if "seed" not in req.drop_params:
                self.fail_calls += 1
                raise BadRequestError(
                    'HTTP 400: {"detail":"Unsupported parameter: seed"}',
                    status_code=400,
                )
            return ChatResponse(
                text="B", raw_text="B",
                usage=Usage(prompt_tokens=10, completion_tokens=1, total_tokens=11),
                latency_ms=3.0,
            )

        async def list_models(self): return []

    items = [
        {"id": str(i), "question": f"q{i}", "choices": ["A", "B", "C", "D"],
         "answer": "B", "subject": "x"}
        for i in range(4)
    ]
    bench = _MiniMC()
    adapter = _SeedRejectingAdapter()

    r = await bench.run(adapter, items, model="probe-m", concurrency=2, thinking="off")

    # Every item ended ok (1 retry per failed item, then learned drop sticks).
    assert r.error_breakdown.get("ok") == 4
    assert r.accuracy == pytest.approx(1.0)
    # Result surfaces the learned key.
    assert "seed" in r.learned_drop_params
    # The first call had no `seed` drop; later calls all do.
    assert any("seed" not in d for d in adapter.last_drop_params[:2])
    assert all("seed" in d for d in adapter.last_drop_params[2:])
    # Persistence: file should now hold seed for probe-m.
    persisted = tmp_path / "learned.json"
    assert persisted.exists()
    import json as _json
    data = _json.loads(persisted.read_text())
    assert "seed" in data["models"]["probe-m"]["drop_params"]
