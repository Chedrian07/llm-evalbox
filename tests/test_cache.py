# SPDX-License-Identifier: Apache-2.0
"""Response cache: key stability, hit/miss, EVALBOX_NO_CACHE."""

from __future__ import annotations

import pytest

from llm_evalbox.cache.responses import ResponseCache, cache_key
from llm_evalbox.core.messages import Message
from llm_evalbox.core.request import ChatResponse, Usage


def _key_args(**overrides):
    base = dict(
        adapter_name="chat_completions",
        base_url="https://api.test/v1",
        model="gpt-4o-mini",
        messages=[Message(role="user", content="hi")],
        sampling={"temperature": 0.0, "max_tokens": 8, "seed": 42},
        thinking_mode="auto",
        benchmark_name="mmlu",
    )
    base.update(overrides)
    return base


def test_key_stable_across_calls():
    a = cache_key(**_key_args())
    b = cache_key(**_key_args())
    assert a == b


def test_key_stable_with_path_variations_in_base_url():
    a = cache_key(**_key_args(base_url="https://api.test/v1"))
    b = cache_key(**_key_args(base_url="https://api.test/v1/"))
    c = cache_key(**_key_args(base_url="https://api.test/v1/anything"))
    assert a == b == c, "host-only normalization should make these equal"


def test_key_changes_on_message_change():
    a = cache_key(**_key_args())
    b = cache_key(**_key_args(messages=[Message(role="user", content="bye")]))
    assert a != b


def test_key_changes_on_thinking_mode():
    a = cache_key(**_key_args(thinking_mode="off"))
    b = cache_key(**_key_args(thinking_mode="on"))
    assert a != b


def test_key_changes_on_benchmark_version():
    a = cache_key(**_key_args(benchmark_version="v1"))
    b = cache_key(**_key_args(benchmark_version="v2"))
    assert a != b


def test_sampling_none_values_dont_change_key():
    a = cache_key(**_key_args(sampling={"temperature": 0.0, "top_p": None}))
    b = cache_key(**_key_args(sampling={"temperature": 0.0}))
    assert a == b


def test_put_and_get_roundtrip(tmp_path):
    cache = ResponseCache(enabled=True, root=tmp_path)
    key = cache_key(**_key_args())
    resp = ChatResponse(
        text="OK",
        raw_text="OK",
        usage=Usage(prompt_tokens=10, completion_tokens=1, total_tokens=11),
        latency_ms=42.0,
    )
    assert cache.get(key) is None  # miss
    cache.put(key, resp)
    hit = cache.get(key)
    assert hit is not None
    assert hit.text == "OK"
    assert hit.cache_hit is True
    assert hit.latency_ms == 0.0  # reset on hit
    # Original response usage preserved
    assert hit.usage.prompt_tokens == 10


def test_disabled_cache_is_noop(tmp_path):
    cache = ResponseCache(enabled=False, root=tmp_path)
    key = cache_key(**_key_args())
    resp = ChatResponse(text="OK", usage=Usage())
    cache.put(key, resp)
    assert cache.get(key) is None


def test_from_env_respects_no_cache(monkeypatch):
    monkeypatch.setenv("EVALBOX_NO_CACHE", "1")
    c = ResponseCache.from_env()
    assert c.enabled is False
    monkeypatch.delenv("EVALBOX_NO_CACHE")
    c2 = ResponseCache.from_env()
    assert c2.enabled is True


def test_corrupt_cache_file_is_skipped(tmp_path):
    cache = ResponseCache(enabled=True, root=tmp_path)
    key = "deadbeef" * 8
    p = cache._path(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("not json", encoding="utf-8")
    assert cache.get(key) is None  # gracefully returns miss


@pytest.mark.asyncio
async def test_run_with_cache_hits_skips_network(tmp_path, mini_mmlu):
    """Second run() with the same args should not call adapter.chat."""
    from llm_evalbox.adapters.base import ChatAdapter
    from llm_evalbox.core.request import ChatResponse, Usage
    from llm_evalbox.eval.base import BaseBenchmark
    from llm_evalbox.eval.extract import extract_mc_answer

    class _CountingAdapter(ChatAdapter):
        name = "chat_completions"

        def __init__(self):
            super().__init__()
            self.calls = 0

        async def chat(self, req):
            self.calls += 1
            return ChatResponse(
                text="B", raw_text="B",
                usage=Usage(prompt_tokens=10, completion_tokens=1, total_tokens=11),
                latency_ms=5.0,
            )

        async def list_models(self): return []

    class _MiniMC(BaseBenchmark):
        name = "mmlu"

        async def load_dataset(self, sample_size=0): return []
        def format_prompt(self, item): return [Message(role="user", content=f"q{item['id']}")]
        def extract_answer(self, response, item): return extract_mc_answer(response, "ABCD")
        def check_answer(self, predicted, item): return predicted == item["answer"]

    cache = ResponseCache(enabled=True, root=tmp_path)
    bench = _MiniMC()
    adapter = _CountingAdapter()

    # First run — populates cache
    r1 = await bench.run(adapter, mini_mmlu, model="m", concurrency=2, thinking="off",
                         cache=cache, base_url="https://api.test/v1")
    n1 = adapter.calls
    assert n1 == len(mini_mmlu)
    assert r1.accuracy > 0  # the answer letter happens to match some items

    # Second run — should hit cache for every item (no new chat calls)
    r2 = await bench.run(adapter, mini_mmlu, model="m", concurrency=2, thinking="off",
                         cache=cache, base_url="https://api.test/v1")
    assert adapter.calls == n1  # no additional network calls
    # All cache hits
    assert all(q.cache_hit for q in r2.questions)
