# SPDX-License-Identifier: Apache-2.0
"""--prompt-cache-aware: stable system prefix prepended; cache_hit_rate emitted."""

from __future__ import annotations

import pytest

from llm_evalbox.adapters.base import ChatAdapter
from llm_evalbox.core.messages import Message
from llm_evalbox.core.request import ChatResponse, ModelInfo, Usage
from llm_evalbox.eval._cache_aware import PROMPT_CACHE_PREFIX
from llm_evalbox.eval.base import BaseBenchmark
from llm_evalbox.eval.extract import extract_mc_answer


class _CapturingAdapter(ChatAdapter):
    name = "capture"

    def __init__(self):
        super().__init__()
        self.captured: list[list[Message]] = []
        # Returns the same (correct) answer + reports cached_prompt_tokens
        # mounting after the first call, so we can verify the rate field.

    async def chat(self, req):
        self.captured.append(list(req.messages))
        n = len(self.captured)
        # Pretend the provider's prompt cache kicks in after call #1.
        cached = 1000 if n > 1 else 0
        return ChatResponse(
            text="B", raw_text="B",
            usage=Usage(prompt_tokens=1500, completion_tokens=1,
                        cached_prompt_tokens=cached, total_tokens=1501),
            latency_ms=5.0,
        )

    async def list_models(self) -> list[ModelInfo]:
        return []


class _MiniMC(BaseBenchmark):
    name = "mini_mc"

    async def load_dataset(self, sample_size: int = 0):
        return []

    def format_prompt(self, item):
        return [Message(role="user", content=f"Q: {item['question']}")]

    def extract_answer(self, response, item):
        return extract_mc_answer(response, "ABCD")

    def check_answer(self, predicted, item):
        return predicted == item["answer"]


@pytest.mark.asyncio
async def test_prompt_cache_aware_prepends_prefix():
    bench = _MiniMC()
    adapter = _CapturingAdapter()
    items = [{"id": str(i), "question": f"q{i}", "answer": "B"} for i in range(3)]
    await bench.run(
        adapter, items, model="m", concurrency=1, thinking="off",
        prompt_cache_aware=True,
    )
    # Every captured message list should start with the cache prefix.
    for msgs in adapter.captured:
        assert msgs[0].role == "system"
        assert msgs[0].content == PROMPT_CACHE_PREFIX


@pytest.mark.asyncio
async def test_prompt_cache_aware_off_no_prefix():
    bench = _MiniMC()
    adapter = _CapturingAdapter()
    items = [{"id": str(i), "question": f"q{i}", "answer": "B"} for i in range(2)]
    await bench.run(
        adapter, items, model="m", concurrency=1, thinking="off",
    )
    for msgs in adapter.captured:
        # No system prefix in any captured request.
        assert not (msgs and msgs[0].role == "system" and msgs[0].content == PROMPT_CACHE_PREFIX)
