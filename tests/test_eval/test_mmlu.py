# SPDX-License-Identifier: Apache-2.0
"""MMLU end-to-end with a mini in-memory dataset (no network)."""

from __future__ import annotations

import pytest

from llm_evalbox.adapters.base import ChatAdapter
from llm_evalbox.core.request import ChatRequest, ChatResponse, ModelInfo, Usage
from llm_evalbox.eval.mmlu import MMLUBenchmark


class _ChoiceAdapter(ChatAdapter):
    """Always returns the correct letter — exercises format_prompt + extract_answer."""

    name = "choice"

    async def chat(self, req: ChatRequest) -> ChatResponse:
        # The user prompt ends with the question. Find the answer line "X. <correct>".
        # For testing, we cheat: the conftest always wires "answer letter" into prompt
        # by using the test fixture's `answer` field encoded as: the LAST "Answer: X"
        # appears in few-shot, so we instead just look for the canonical correct
        # marker we'll splice into prompts via the bench's questions.
        prompt = req.messages[-1].content
        # Find the "Answer:" line and *then* the user's question is below it; we don't
        # know the gold answer here. Instead we read the test-injected "(GOLD=X)" suffix.
        import re
        m = re.search(r"\(GOLD=([A-D])\)", prompt)
        ans = m.group(1) if m else "A"
        return ChatResponse(
            text=ans,
            raw_text=ans,
            finish_reason="stop",
            usage=Usage(prompt_tokens=10, completion_tokens=1, total_tokens=11),
            latency_ms=5.0,
        )

    async def list_models(self) -> list[ModelInfo]:
        return []


@pytest.mark.asyncio
async def test_mmlu_format_and_score(monkeypatch):
    bench = MMLUBenchmark()

    # Patch ensure_dataset/load_jsonl: bypass network entirely.
    items_test = [
        {"question": "2+2? (GOLD=B)", "choices": ["3", "4", "5", "6"], "answer": 1, "subject": "math"},
        {"question": "Capital of France? (GOLD=B)", "choices": ["Berlin", "Paris", "Rome", "Madrid"],
         "answer": 1, "subject": "geo"},
    ]
    items_dev: list[dict] = []

    def _ensure(name):
        return {"mmlu_test.jsonl": "/tmp/x.jsonl", "mmlu_dev.jsonl": "/tmp/y.jsonl"}

    def _load(path):
        return items_test if str(path).endswith("x.jsonl") else items_dev

    import llm_evalbox.eval.mmlu as mmlu_mod
    monkeypatch.setattr(mmlu_mod, "ensure_dataset", _ensure)
    monkeypatch.setattr(mmlu_mod, "load_jsonl", _load)

    items = await bench.load_dataset(0)
    assert len(items) == 2
    # answer should now be a letter
    assert items[0]["answer"] == "B"

    adapter = _ChoiceAdapter()
    result = await bench.run(adapter, items, model="mock-mmlu", concurrency=2, thinking="off")
    assert result.accuracy == pytest.approx(1.0)
    assert result.category_scores is not None
    assert "math" in result.category_scores or "geo" in result.category_scores
