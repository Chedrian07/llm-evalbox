# SPDX-License-Identifier: Apache-2.0
"""Pydantic request/response shapes for the web API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConnectionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    base_url: str
    model: str
    adapter: str = "auto"
    api_key_env: str | None = None
    api_key: str | None = None  # only honored when set; not echoed back
    extra_headers: dict[str, str] = Field(default_factory=dict)


class CapabilityInfo(BaseModel):
    accepts_temperature: bool
    accepts_top_p: bool
    accepts_top_k: bool
    accepts_seed: bool
    accepts_reasoning_effort: bool
    use_max_completion_tokens: bool
    notes: str = ""


class ConnectionResponse(BaseModel):
    ok: bool
    adapter: str
    model_listed: bool | None = None
    model_count: int | None = None
    latency_ms: float | None = None
    finish_reason: str | None = None
    thinking_observed: bool | None = None
    text_preview: str | None = None
    capability: CapabilityInfo
    learned_drop_params: list[str] = Field(default_factory=list)
    error: str | None = None


class BenchmarkInfo(BaseModel):
    name: str
    quick_size: int
    is_code_bench: bool
    category: str  # knowledge | reasoning | math | coding | truthful | multilingual | safety
    license: str | None = None


class PricingEstimateRequest(BaseModel):
    model: str
    benchmarks: list[str]
    samples: int = 200
    concurrency: int = 8
    thinking: Literal["auto", "on", "off"] = "auto"


class PricingEstimateResponse(BaseModel):
    est_prompt_tokens: int
    est_completion_tokens: int
    est_reasoning_tokens: int
    est_cost_usd: float | None
    est_seconds: int


class RunCreateRequest(BaseModel):
    connection: ConnectionRequest
    benches: list[str]
    samples: int = 200
    concurrency: int = 8
    thinking: Literal["auto", "on", "off"] = "auto"
    no_thinking_rerun: bool = False
    prompt_cache_aware: bool = False
    accept_code_exec: bool = False
    strict_failures: bool = False
    no_cache: bool = False
    max_cost_usd: float | None = None
    sampling: dict[str, Any] = Field(default_factory=dict)
    drop_params: list[str] = Field(default_factory=list)


class RunCreateResponse(BaseModel):
    run_id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]


class RunSummary(BaseModel):
    run_id: str
    status: str
    started_at: str
    finished_at: str | None
    model: str
    base_url: str
