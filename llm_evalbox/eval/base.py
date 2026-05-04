# SPDX-License-Identifier: Apache-2.0
"""BaseBenchmark + per-question / per-benchmark result records.

Concrete benchmarks implement load_dataset / format_prompt / extract_answer /
check_answer. The base `run()` handles concurrency, thinking auto-detection,
error classification, and progress callbacks.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from llm_evalbox.adapters.base import ChatAdapter
from llm_evalbox.adapters.capabilities import (
    KNOWN_SAMPLING_KEYS,
    parse_unsupported_param_error,
)
from llm_evalbox.core.exceptions import AdapterError, BadRequestError
from llm_evalbox.core.messages import Message
from llm_evalbox.core.request import ChatRequest, ChatResponse, Usage

logger = logging.getLogger(__name__)


ErrorKind = str  # "ok" | "wrong_answer" | "timeout" | "memory" |
                 # "runtime_error" | "compile_error" | "generation_failed" | "network"


@dataclass
class QuestionResult:
    question_id: str
    correct: bool
    expected: str
    predicted: str
    latency_ms: float
    error_kind: ErrorKind = "ok"
    category: str | None = None
    raw_response: str = ""
    reasoning_text: str = ""
    prompt_text: str = ""
    usage: Usage = field(default_factory=Usage)
    cache_hit: bool = False


@dataclass
class BenchmarkResult:
    benchmark_name: str
    samples: int
    accuracy: float
    correct_count: int
    accuracy_ci95: tuple[float, float]
    duration_s: float
    p50_latency_ms: float
    p95_latency_ms: float
    usage_total: Usage
    error_breakdown: dict[str, int]
    category_scores: dict[str, float] | None
    thinking_used: bool
    denominator_policy: str = "lenient"  # "lenient" (ok|wrong_answer) | "strict" (all)
    cost_usd_estimated: float | None = None
    questions: list[QuestionResult] = field(default_factory=list)
    # Sampling keys the run learned to drop after the gateway returned 4xx.
    # Persisted via `remember_learned()` for the model so future runs skip.
    learned_drop_params: list[str] = field(default_factory=list)


@dataclass
class SamplingOverrides:
    """User-supplied sampling overrides (CLI / env / profile).

    If any value is non-None, the benchmark will *not* enforce strict
    determinism — strict mode (`temperature=0`, no penalties) is only forced
    when `strict_deterministic=True` on the run call.
    """

    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    max_tokens: int | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    repetition_penalty: float | None = None
    reasoning_effort: str | None = None

    def has_any(self) -> bool:
        return any(getattr(self, k) is not None for k in self.__annotations__)


def _wilson_ci(correct: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 95% CI for a binomial proportion."""
    if total == 0:
        return (0.0, 0.0)
    p = correct / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = (z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * pct
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] + (s[c] - s[f]) * (k - f)


class BaseBenchmark(ABC):
    name: str = ""
    quick_size: int = 200  # PLAN.md §18.2 — uniform default

    # ------------------------------------------------------------------ hook
    @abstractmethod
    async def load_dataset(self, sample_size: int = 0) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def format_prompt(self, item: dict) -> list[Message]:
        ...

    @abstractmethod
    def extract_answer(self, response: str, item: dict) -> str:
        ...

    @abstractmethod
    def check_answer(self, predicted: str, item: dict) -> bool:
        ...

    def get_max_tokens(self) -> int:
        return 128

    def get_category(self, item: dict) -> str | None:
        return None

    def is_code_bench(self) -> bool:
        return False

    # ---------------------------------------------------- request construction
    def _build_request(
        self,
        *,
        model: str,
        item: dict,
        sampling: SamplingOverrides | None,
        thinking_mode: str,
        strict: bool,
        prompt_cache_aware: bool = False,
    ) -> ChatRequest:
        msgs = self.format_prompt(item)
        if prompt_cache_aware:
            from llm_evalbox.eval._cache_aware import PROMPT_CACHE_PREFIX
            msgs = [Message(role="system", content=PROMPT_CACHE_PREFIX), *msgs]
        kwargs: dict[str, Any] = {}
        if sampling and not strict:
            for k in (
                "temperature", "top_p", "top_k", "max_tokens",
                "presence_penalty", "frequency_penalty", "repetition_penalty",
                "reasoning_effort",
            ):
                v = getattr(sampling, k, None)
                if v is not None:
                    kwargs[k] = v
        if strict:
            kwargs["temperature"] = 0.0
            kwargs["presence_penalty"] = 0.0
            kwargs["frequency_penalty"] = 0.0
            kwargs["repetition_penalty"] = 1.0

        if "max_tokens" not in kwargs:
            kwargs["max_tokens"] = self.get_max_tokens()

        return ChatRequest(
            model=model,
            messages=list(msgs),
            thinking=thinking_mode,
            **kwargs,
        )

    # --------------------------------------------------------- per-question
    async def _eval_single(
        self,
        adapter: ChatAdapter,
        item: dict,
        index: int,
        *,
        model: str,
        sampling: SamplingOverrides | None,
        thinking_mode: str,
        strict: bool,
        sem: asyncio.Semaphore,
        cache: Any | None = None,
        base_url: str = "",
        prompt_cache_aware: bool = False,
        runtime_drops: set[str] | None = None,
    ) -> tuple[int, dict, ChatResponse | None, str, str]:
        """Run one item.

        Returns (index, item, response_or_none, error_kind_for_network_path, prompt_text).
        Code-execution scoring is *not* done here — only the model call. The
        caller (run) walks results and calls check_answer; code benches
        override `_score_response` to plug sandbox.

        `runtime_drops` is a shared, mutable set updated by `run()` whenever the
        gateway tells us a sampling key is unsupported. We merge it into the
        request before each call so subsequent items skip the offender, and we
        retry the current item once after learning a new key.
        """
        req = self._build_request(
            model=model,
            item=item,
            sampling=sampling,
            thinking_mode=thinking_mode,
            strict=strict,
            prompt_cache_aware=prompt_cache_aware,
        )
        if runtime_drops:
            req = req.model_copy(update={
                "drop_params": sorted(set(req.drop_params) | runtime_drops)
            })
        prompt_text = "\n".join(m.content for m in req.messages)

        # Cache lookup (response cache, PLAN §13.3) — gated on caller passing
        # a cache instance + a base_url (so the key reflects the gateway).
        cache_k: str | None = None
        if cache is not None and getattr(cache, "enabled", False):
            from llm_evalbox.cache.responses import cache_key as _build_cache_key
            sampling_dict = req.model_dump(
                include={
                    "temperature", "top_p", "top_k", "max_tokens",
                    "presence_penalty", "frequency_penalty", "repetition_penalty",
                    "reasoning_effort", "seed", "stop",
                }
            )
            cache_k = _build_cache_key(
                adapter_name=adapter.name,
                base_url=base_url,
                model=model,
                messages=req.messages,
                sampling=sampling_dict,
                thinking_mode=thinking_mode,
                benchmark_name=self.name,
            )
            hit = cache.get(cache_k)
            if hit is not None:
                return index, item, hit, "ok", prompt_text

        async with sem:
            try:
                resp = await adapter.chat(req)
                if cache is not None and cache_k is not None:
                    cache.put(cache_k, resp)
                return index, item, resp, "ok", prompt_text
            except BadRequestError as e:
                # Adaptive learning: the gateway told us a key it doesn't accept.
                # We retry with `runtime_drops` merged in. There are two cases:
                #   1. We just learned a new key — log it.
                #   2. A sibling task (same batch, racing) already learned the
                #      same key while we were in flight; we didn't add anything
                #      new, but `runtime_drops` is now bigger than this
                #      request's `drop_params`, so a retry is still worthwhile.
                # Both cases share the same retry path.
                unsupported = parse_unsupported_param_error(str(e))
                detected = unsupported & set(KNOWN_SAMPLING_KEYS)
                new_drops: set[str] = set()
                if runtime_drops is not None:
                    new_drops = detected - runtime_drops
                    if new_drops:
                        runtime_drops.update(new_drops)
                already_known = (
                    runtime_drops is not None
                    and bool(runtime_drops - set(req.drop_params))
                )
                if new_drops or already_known:
                    if new_drops:
                        logger.warning(
                            "item %d: 4xx, learned drop_params=%s, retrying",
                            index, sorted(new_drops),
                        )
                    else:
                        logger.info(
                            "item %d: 4xx, retrying with shared drops=%s",
                            index, sorted(runtime_drops or ()),
                        )
                    retried = req.model_copy(update={
                        "drop_params": sorted(set(req.drop_params) | (runtime_drops or set()))
                    })
                    try:
                        resp = await adapter.chat(retried)
                        if cache is not None and cache_k is not None:
                            cache.put(cache_k, resp)
                        return index, item, resp, "ok", prompt_text
                    except AdapterError as e2:
                        logger.warning(
                            "item %d: retry after learning still failed: %s",
                            index, e2,
                        )
                        return index, item, None, "network", prompt_text
                logger.warning("adapter 4xx on item %d (no learnable key): %s", index, e)
                return index, item, None, "network", prompt_text
            except AdapterError as e:
                logger.warning("adapter error on item %d: %s", index, e)
                return index, item, None, "network", prompt_text
            except Exception as e:
                logger.exception("unexpected error on item %d: %s", index, e)
                return index, item, None, "generation_failed", prompt_text

    # ---------------------------------------------- score one chat response
    def _score_response(
        self, item: dict, resp: ChatResponse
    ) -> tuple[bool, str, ErrorKind]:
        """Default scoring path for non-code benchmarks.

        Returns (is_correct, predicted_string, error_kind).
        """
        try:
            predicted = self.extract_answer(resp.text, item)
        except Exception as e:
            logger.warning("extract_answer failed: %s", e)
            return False, "", "generation_failed"
        try:
            correct = self.check_answer(predicted, item)
        except Exception as e:
            logger.warning("check_answer failed: %s", e)
            return False, predicted, "generation_failed"
        return correct, predicted, ("ok" if correct else "wrong_answer")

    # -------------------------------------------------------- main entry
    async def run(
        self,
        adapter: ChatAdapter,
        items: list[dict],
        *,
        model: str,
        on_progress: Callable[[int, int, dict[str, Any]], Awaitable[None]] | None = None,
        on_item: Callable[[QuestionResult, int, int], Awaitable[None]] | None = None,
        concurrency: int = 8,
        sampling: SamplingOverrides | None = None,
        thinking: str = "auto",
        strict_deterministic: bool = False,
        strict_failures: bool = False,
        no_thinking_rerun: bool = False,
        cache: Any | None = None,
        base_url: str = "",
        prompt_cache_aware: bool = False,
        initial_drop_params: list[str] | None = None,
    ) -> BenchmarkResult:
        """Run the benchmark. Returns aggregated `BenchmarkResult`.

        Auto-thinking flow (`thinking="auto"`):
          - First batch (size = concurrency) runs with mode "auto".
          - If any response carries observed thinking, mode flips to "on" for
            subsequent items and (unless `no_thinking_rerun=True`) the first
            batch is re-run so its truncated answers don't pollute accuracy.

        Denominator policy:
          - `strict_failures=False` (lenient, default): only `ok`+`wrong_answer`
            count toward the denominator. Sandbox/network errors are excluded.
            Use this for quick comparisons where infra noise shouldn't hurt scores.
          - `strict_failures=True` (strict): all questions count, including
            sandbox failures (`compile_error`, `runtime_error`, `timeout`,
            `memory`), `generation_failed`, and `network`. Use this for
            academic comparison against published numbers.
        """
        if sampling is not None and sampling.has_any() and strict_deterministic:
            logger.warning("strict_deterministic=True overrides sampling overrides")
            sampling = None

        sem = asyncio.Semaphore(concurrency)
        results_by_idx: dict[int, QuestionResult] = {}
        completed = 0
        total = len(items)
        start = time.time()

        # Shared mutable across all parallel items in this run. Seeded with any
        # caller-supplied drops (e.g. the Web UI's lookup_learned for the
        # current model). New entries are added when adapter.chat raises
        # BadRequestError and parse_unsupported_param_error finds a sampling key.
        runtime_drops: set[str] = set(initial_drop_params or [])

        thinking_mode = thinking
        thinking_used = thinking == "on"
        first_batch_indices: list[int] = []

        # Phase 1: process items in chunks of `concurrency` (so the first batch
        # gives us a clean signal for thinking auto-detection).
        cursor = 0
        first = True
        while cursor < total:
            batch_size = min(concurrency, total - cursor)
            batch_indices = list(range(cursor, cursor + batch_size))
            if first:
                first_batch_indices = list(batch_indices)

            tasks = [
                self._eval_single(
                    adapter, items[i], i,
                    model=model,
                    sampling=sampling,
                    thinking_mode=thinking_mode,
                    strict=strict_deterministic,
                    sem=sem,
                    cache=cache,
                    base_url=base_url,
                    prompt_cache_aware=prompt_cache_aware,
                    runtime_drops=runtime_drops,
                )
                for i in batch_indices
            ]
            batch_results = await asyncio.gather(*tasks)

            # Auto-switch decision on first batch
            if first and thinking == "auto":
                observed = any(
                    (r is not None and r.thinking_observed)
                    for _, _, r, _, _ in batch_results
                )
                if observed:
                    logger.info(
                        "%s: thinking observed in first batch → switching to on", self.name
                    )
                    thinking_mode = "on"
                    thinking_used = True
                    if not no_thinking_rerun:
                        # Re-run the first batch with thinking on — original
                        # responses likely got truncated.
                        rerun_tasks = [
                            self._eval_single(
                                adapter, items[i], i,
                                model=model,
                                sampling=sampling,
                                thinking_mode=thinking_mode,
                                strict=strict_deterministic,
                                sem=sem,
                                cache=cache,
                                base_url=base_url,
                                prompt_cache_aware=prompt_cache_aware,
                                runtime_drops=runtime_drops,
                            )
                            for i in batch_indices
                        ]
                        batch_results = await asyncio.gather(*rerun_tasks)
            first = False

            # Score and accumulate
            scored_in_batch: list[tuple[int, QuestionResult]] = []
            for idx, item, resp, err_kind, prompt_text in batch_results:
                qid = str(item.get("id", idx))
                cat = self.get_category(item)
                expected = str(item.get("answer", ""))

                if resp is None:
                    qr = QuestionResult(
                        question_id=qid,
                        correct=False,
                        expected=expected,
                        predicted="",
                        latency_ms=0.0,
                        error_kind=err_kind,
                        category=cat,
                        prompt_text=prompt_text,
                    )
                else:
                    correct, predicted, kind = self._score_response(item, resp)
                    qr = QuestionResult(
                        question_id=qid,
                        correct=correct,
                        expected=expected,
                        predicted=predicted,
                        latency_ms=resp.latency_ms,
                        error_kind=kind,
                        category=cat,
                        raw_response=resp.text,
                        reasoning_text=resp.reasoning_text,
                        prompt_text=prompt_text,
                        usage=resp.usage,
                        cache_hit=resp.cache_hit,
                    )
                results_by_idx[idx] = qr
                scored_in_batch.append((idx, qr))

            # Emit per-item callback after scoring so the SSE stream can push
            # prompt/response previews into the live log panel. Best-effort —
            # caller failures don't break the run.
            if on_item is not None:
                for idx, qr in scored_in_batch:
                    try:
                        await on_item(qr, idx, total)
                    except Exception:  # pragma: no cover
                        logger.warning("on_item callback raised; ignoring", exc_info=True)

            completed += batch_size
            if on_progress is not None:
                running_correct = sum(1 for r in results_by_idx.values() if r.correct)
                payload = {
                    "current": completed,
                    "total": total,
                    "running_accuracy": (running_correct / completed) if completed else 0.0,
                    "thinking_used": thinking_used,
                }
                await on_progress(completed, total, payload)
            cursor += batch_size

        # Aggregate
        ordered = [results_by_idx[i] for i in range(total)]

        # accuracy denominator policy:
        #   - lenient (default): only ok | wrong_answer (sandbox/network excluded)
        #   - strict (--strict-failures): all rows count
        if strict_failures:
            scored = ordered
        else:
            scored = [r for r in ordered if r.error_kind in ("ok", "wrong_answer")]
        correct_count = sum(1 for r in scored if r.correct)
        denom = len(scored)
        accuracy = (correct_count / denom) if denom else 0.0
        ci = _wilson_ci(correct_count, denom)

        latencies = [r.latency_ms for r in ordered if r.latency_ms > 0]
        usage_total = Usage()
        for r in ordered:
            usage_total = usage_total + r.usage

        error_breakdown: dict[str, int] = {}
        for r in ordered:
            error_breakdown[r.error_kind] = error_breakdown.get(r.error_kind, 0) + 1

        category_scores: dict[str, float] | None = None
        cat_total: dict[str, int] = {}
        cat_correct: dict[str, int] = {}
        for r in scored:
            if r.category is None:
                continue
            cat_total[r.category] = cat_total.get(r.category, 0) + 1
            if r.correct:
                cat_correct[r.category] = cat_correct.get(r.category, 0) + 1
        if cat_total:
            category_scores = {
                c: (cat_correct.get(c, 0) / cat_total[c]) for c in sorted(cat_total)
            }

        # Persist anything we learned at runtime so future runs skip the
        # offending keys from the start. We only persist new keys (those not
        # in the caller-supplied initial set).
        learned_new = sorted(runtime_drops - set(initial_drop_params or []))
        if learned_new:
            try:
                # Merge with any existing record so we don't shrink it.
                from llm_evalbox.adapters.learned import lookup as _lookup_learned
                from llm_evalbox.adapters.learned import remember as _remember_learned
                existing = set(_lookup_learned(model))
                merged = sorted(existing | set(learned_new))
                _remember_learned(model, merged)
                logger.info(
                    "%s: persisted learned drop_params=%s for model=%s",
                    self.name, learned_new, model,
                )
            except Exception as e:  # pragma: no cover — disk write best-effort
                logger.warning("could not persist learned drop_params: %s", e)

        return BenchmarkResult(
            benchmark_name=self.name,
            samples=total,
            accuracy=accuracy,
            correct_count=correct_count,
            accuracy_ci95=ci,
            duration_s=time.time() - start,
            p50_latency_ms=_percentile(latencies, 0.5),
            p95_latency_ms=_percentile(latencies, 0.95),
            usage_total=usage_total,
            error_breakdown=error_breakdown,
            category_scores=category_scores,
            thinking_used=thinking_used,
            denominator_policy="strict" if strict_failures else "lenient",
            questions=ordered,
            learned_drop_params=sorted(runtime_drops),
        )
