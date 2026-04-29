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


def test_wilson_ci_bounds():
    from llm_evalbox.eval.base import _wilson_ci
    lo, hi = _wilson_ci(50, 100)
    assert 0 <= lo <= 0.5 <= hi <= 1
    lo, hi = _wilson_ci(0, 0)
    assert (lo, hi) == (0.0, 0.0)
