# SPDX-License-Identifier: Apache-2.0
"""result.json schema v1 — see PLAN.md §7."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_evalbox.eval.base import BenchmarkResult, QuestionResult

SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _question_to_dict(q: QuestionResult, *, include_raw: bool) -> dict[str, Any]:
    d = {
        "id": q.question_id,
        "correct": q.correct,
        "expected": q.expected,
        "predicted": q.predicted,
        "latency_ms": q.latency_ms,
        "error_kind": q.error_kind,
        "category": q.category,
        "usage": {
            "prompt_tokens": q.usage.prompt_tokens,
            "completion_tokens": q.usage.completion_tokens,
            "reasoning_tokens": q.usage.reasoning_tokens,
            "cached_prompt_tokens": q.usage.cached_prompt_tokens,
        },
        "cache_hit": q.cache_hit,
    }
    if include_raw:
        d["prompt_text"] = q.prompt_text
        d["raw_response"] = q.raw_response
        d["reasoning_text"] = q.reasoning_text
    return d


def _benchmark_to_dict(b: BenchmarkResult, *, cost: float | None) -> dict[str, Any]:
    prompt_t = b.usage_total.prompt_tokens
    cached_t = b.usage_total.cached_prompt_tokens
    rate = (cached_t / prompt_t) if prompt_t > 0 else 0.0
    return {
        "name": b.benchmark_name,
        "samples": b.samples,
        "accuracy": b.accuracy,
        "accuracy_ci95": list(b.accuracy_ci95),
        "correct_count": b.correct_count,
        "category_scores": b.category_scores or {},
        "error_breakdown": dict(b.error_breakdown),
        "latency_ms": {"p50": b.p50_latency_ms, "p95": b.p95_latency_ms},
        "tokens": {
            "prompt": b.usage_total.prompt_tokens,
            "completion": b.usage_total.completion_tokens,
            "reasoning": b.usage_total.reasoning_tokens,
            "cached_prompt": b.usage_total.cached_prompt_tokens,
            "reasoning_estimated": b.usage_total.reasoning_estimated,
        },
        "cost_usd_estimated": cost,
        "duration_s": b.duration_s,
        "thinking_used": b.thinking_used,
        "denominator_policy": b.denominator_policy,
        "cache_hits": sum(1 for q in b.questions if q.cache_hit),
        "prompt_cache_hit_rate": round(rate, 4),
    }


def serialize_result(
    *,
    run_id: str,
    started_at: str,
    finished_at: str | None,
    seed: int,
    provider: dict[str, Any],
    sampling: dict[str, Any],
    thinking: dict[str, Any],
    capability: dict[str, Any],
    strict_deterministic: bool,
    strict_failures: bool,
    benchmarks: list[BenchmarkResult],
    costs: dict[str, float | None],
) -> dict[str, Any]:
    bench_dicts = [_benchmark_to_dict(b, cost=costs.get(b.benchmark_name)) for b in benchmarks]
    accuracies = [b["accuracy"] for b in bench_dicts]
    macro_acc = sum(accuracies) / len(accuracies) if accuracies else 0.0

    total_prompt = sum(b["tokens"]["prompt"] for b in bench_dicts)
    total_completion = sum(b["tokens"]["completion"] for b in bench_dicts)
    total_reasoning = sum(b["tokens"]["reasoning"] for b in bench_dicts)
    total_cached = sum(b["tokens"]["cached_prompt"] for b in bench_dicts)

    cost_known = [b["cost_usd_estimated"] for b in bench_dicts if b["cost_usd_estimated"] is not None]
    total_cost: float | None = sum(cost_known) if cost_known else None

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at or _utc_now(),
        "seed": seed,
        "provider": provider,
        "sampling": sampling,
        "thinking": thinking,
        "capability": capability,
        "strict_deterministic": strict_deterministic,
        "strict_failures": strict_failures,
        "benchmarks": bench_dicts,
        "totals": {
            "accuracy_macro": macro_acc,
            "tokens": {
                "prompt": total_prompt,
                "completion": total_completion,
                "reasoning": total_reasoning,
                "cached_prompt": total_cached,
            },
            "cost_usd_estimated": total_cost,
        },
    }


def write_result_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def write_result_questions_jsonl(
    path: Path,
    benchmarks: list[BenchmarkResult],
    *,
    include_raw: bool = True,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for b in benchmarks:
            for q in b.questions:
                d = _question_to_dict(q, include_raw=include_raw)
                d["benchmark"] = b.benchmark_name
                f.write(json.dumps(d, ensure_ascii=False))
                f.write("\n")
