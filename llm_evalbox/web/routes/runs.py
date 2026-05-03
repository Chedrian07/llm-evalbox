# SPDX-License-Identifier: Apache-2.0
"""POST /api/runs (start), GET /api/runs/{id}/events (SSE), DELETE (cancel)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from llm_evalbox.adapters import resolve_adapter
from llm_evalbox.adapters.auth import resolve_api_key
from llm_evalbox.adapters.capabilities import capability_for
from llm_evalbox.adapters.learned import lookup as lookup_learned
from llm_evalbox.cache import ResponseCache
from llm_evalbox.core.exceptions import EvalBoxError
from llm_evalbox.eval import BENCHMARKS, get_benchmark
from llm_evalbox.eval._sandbox.policy import accept_code_exec
from llm_evalbox.eval.base import SamplingOverrides
from llm_evalbox.pricing import cost_for_usage
from llm_evalbox.reports import serialize_result
from llm_evalbox.web.schemas import RunCreateRequest, RunCreateResponse, RunSummary
from llm_evalbox.web.state import RunState, get_registry

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/runs", response_model=RunCreateResponse)
async def create_run(req: RunCreateRequest) -> RunCreateResponse:
    unknown = [b for b in req.benches if b not in BENCHMARKS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"unknown benchmark(s): {unknown}")

    registry = get_registry()
    state = registry.create(req.model_dump())
    state.task = asyncio.create_task(_run_in_background(state, req))
    return RunCreateResponse(run_id=state.run_id, status="queued")


@router.get("/api/runs", response_model=list[RunSummary])
def list_runs() -> list[RunSummary]:
    registry = get_registry()
    out = []
    for s in registry.list():
        out.append(RunSummary(
            run_id=s.run_id, status=s.status,
            started_at=s.started_at, finished_at=s.finished_at,
            model=s.config.get("connection", {}).get("model", ""),
            base_url=s.config.get("connection", {}).get("base_url", ""),
        ))
    return out


@router.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    state = get_registry().get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {
        "run_id": state.run_id,
        "status": state.status,
        "started_at": state.started_at,
        "finished_at": state.finished_at,
        "result": state.final_payload,
    }


@router.delete("/api/runs/{run_id}")
async def cancel_run(run_id: str) -> dict[str, str]:
    ok = await get_registry().cancel(run_id)
    if not ok:
        raise HTTPException(status_code=404, detail="run not found")
    return {"status": "cancelled"}


@router.get("/api/runs/{run_id}/events")
async def run_events(run_id: str, request: Request) -> EventSourceResponse:
    state = get_registry().get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")

    async def event_gen():
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(state.queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                # Heartbeat to keep proxies from killing the connection
                yield {"event": "ping", "data": "{}"}
                continue
            if event.get("type") == "_close":
                break
            yield {"event": event.get("type", "message"), "data": json.dumps(event)}

    return EventSourceResponse(event_gen())


# -------------------------------------------------------- background runner
async def _emit(state: RunState, payload: dict[str, Any]) -> None:
    await state.queue.put(payload)


async def _run_in_background(state: RunState, req: RunCreateRequest) -> None:
    state.status = "running"
    if req.accept_code_exec:
        accept_code_exec()

    try:
        api_key = req.connection.api_key or resolve_api_key(req.connection.api_key_env)
        adapter = resolve_adapter(
            kind=req.connection.adapter,
            base_url=req.connection.base_url,
            api_key=api_key,
            extra_headers=req.connection.extra_headers,
        )
        cache = ResponseCache(enabled=not req.no_cache)

        sampling_obj: SamplingOverrides | None = None
        if req.sampling:
            sampling_obj = SamplingOverrides(
                temperature=req.sampling.get("temperature"),
                top_p=req.sampling.get("top_p"),
                top_k=req.sampling.get("top_k"),
                max_tokens=req.sampling.get("max_tokens"),
                reasoning_effort=req.sampling.get("reasoning_effort"),
            )

        # Seed runtime drops with anything doctor (or a previous run) learned
        # for this model. Combined with the user's explicit drop_params from
        # the request, this is the initial set the eval loop applies.
        seeded_drops = sorted(set(lookup_learned(req.connection.model)) | set(req.drop_params))
        if seeded_drops:
            logger.info(
                "seeding runtime drops for model=%s: %s",
                req.connection.model, seeded_drops,
            )

        results: list = []
        costs: dict[str, float | None] = {}
        cumulative_cost = 0.0
        cumulative_known = False

        try:
            for bench_name in req.benches:
                if state.cancel_event.is_set():
                    break
                bench = get_benchmark(bench_name)
                await _emit(state, {
                    "type": "progress",
                    "phase": "loading",
                    "bench": bench_name,
                    "current": 0,
                    "total": 0,
                })
                items = await bench.load_dataset(req.samples)
                if not items:
                    continue

                async def _on_progress(cur, total, payload, _name=bench_name):
                    await _emit(state, {
                        "type": "progress",
                        "phase": "eval",
                        "bench": _name,
                        "current": cur,
                        "total": total,
                        "running_accuracy": payload.get("running_accuracy", 0.0),
                        "thinking_used": payload.get("thinking_used", False),
                    })

                result = await bench.run(
                    adapter, items,
                    model=req.connection.model,
                    on_progress=_on_progress,
                    concurrency=req.concurrency,
                    sampling=sampling_obj,
                    thinking=req.thinking,
                    no_thinking_rerun=req.no_thinking_rerun,
                    strict_failures=req.strict_failures,
                    cache=cache,
                    base_url=req.connection.base_url,
                    initial_drop_params=seeded_drops,
                )
                results.append(result)
                cost = cost_for_usage(req.connection.model, result.usage_total)
                costs[result.benchmark_name] = cost
                if cost is not None:
                    cumulative_cost += cost
                    cumulative_known = True

                await _emit(state, {
                    "type": "result",
                    "bench": bench_name,
                    "data": {
                        "name": result.benchmark_name,
                        "samples": result.samples,
                        "accuracy": result.accuracy,
                        "accuracy_ci95": list(result.accuracy_ci95),
                        "p50_ms": result.p50_latency_ms,
                        "p95_ms": result.p95_latency_ms,
                        "tokens": {
                            "prompt": result.usage_total.prompt_tokens,
                            "completion": result.usage_total.completion_tokens,
                            "reasoning": result.usage_total.reasoning_tokens,
                            "cached_prompt": result.usage_total.cached_prompt_tokens,
                        },
                        "error_breakdown": dict(result.error_breakdown),
                        "category_scores": result.category_scores or {},
                        "cost_usd": cost,
                        "thinking_used": result.thinking_used,
                        "denominator_policy": result.denominator_policy,
                    },
                })

                if req.max_cost_usd is not None and cumulative_known and cumulative_cost >= req.max_cost_usd:
                    await _emit(state, {
                        "type": "error",
                        "message": f"cost cap reached ({cumulative_cost:.4f} ≥ {req.max_cost_usd})",
                        "retryable": False,
                    })
                    break
        finally:
            await adapter.close()

        cap = capability_for(req.connection.model)
        payload = serialize_result(
            run_id=state.run_id,
            started_at=state.started_at,
            finished_at=None,
            seed=42,
            provider={
                "adapter": adapter.name,
                "base_url": req.connection.base_url,
                "model": req.connection.model,
            },
            sampling={"concurrency": req.concurrency},
            thinking={"mode": req.thinking, "used": any(r.thinking_used for r in results)},
            capability={
                "accepts_temperature": cap.accepts_temperature,
                "accepts_top_k": cap.accepts_top_k,
                "accepts_seed": cap.accepts_seed,
                "accepts_reasoning_effort": cap.accepts_reasoning_effort,
            },
            strict_deterministic=False,
            strict_failures=req.strict_failures,
            benchmarks=results,
            costs=costs,
        )
        state.final_payload = payload
        if state.status != "cancelled":
            state.status = "completed"

        # Persist into the cross-process SQLite history (best effort).
        try:
            from llm_evalbox.cache import upsert_run
            upsert_run(payload)
        except Exception as e:  # pragma: no cover
            logger.warning("history upsert failed: %s", e)

        await _emit(state, {
            "type": "done",
            "summary": {
                "run_id": state.run_id,
                "total_cost_usd": cumulative_cost if cumulative_known else None,
                "benchmarks_completed": len(results),
            },
        })
    except EvalBoxError as e:
        state.status = "failed"
        await _emit(state, {"type": "error", "message": str(e), "retryable": False})
    except Exception as e:
        logger.exception("run %s crashed: %s", state.run_id, e)
        state.status = "failed"
        await _emit(state, {"type": "error", "message": str(e), "retryable": False})
    finally:
        from datetime import datetime, timezone
        state.finished_at = datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        ).replace("+00:00", "Z")
        await _emit(state, {"type": "_close"})
