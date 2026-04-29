# SPDX-License-Identifier: Apache-2.0
"""Normalized request / response DTOs.

Benchmarks see only `ChatRequest` and `ChatResponse`. Provider differences
(Chat Completions vs Responses, capability quirks, thinking encoding) are
absorbed inside adapters.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from llm_evalbox.core.messages import Message

ReasoningEffort = Literal["minimal", "low", "medium", "high"]
ThinkingLiteral = Literal["auto", "on", "off"]


class ChatRequest(BaseModel):
    """Provider-agnostic chat request.

    `extra` is the escape hatch for provider-specific keys; capability
    rules in `adapters/capabilities.py` may strip standard keys per model
    (e.g. o-series rejects `temperature`). `drop_params` is the user-forced
    strip list.
    """

    model_config = ConfigDict(extra="ignore")

    model: str
    messages: list[Message]

    max_tokens: int = 512
    temperature: float = 0.0
    top_p: float | None = None
    top_k: int | None = None
    stop: list[str] | None = None
    seed: int | None = 42

    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    repetition_penalty: float | None = None

    reasoning_effort: ReasoningEffort | None = None
    response_format: dict[str, Any] | None = None

    thinking: ThinkingLiteral = "auto"
    chat_template_kwargs: dict[str, Any] = Field(default_factory=dict)

    extra: dict[str, Any] = Field(default_factory=dict)
    drop_params: list[str] = Field(default_factory=list)


class Usage(BaseModel):
    """Token usage. `reasoning_tokens` and `cached_prompt_tokens` are
    provider-optional; default 0 when unreported."""

    model_config = ConfigDict(extra="ignore")

    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cached_prompt_tokens: int = 0
    total_tokens: int = 0
    reasoning_estimated: bool = False  # provider didn't report; we estimated

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
            cached_prompt_tokens=self.cached_prompt_tokens + other.cached_prompt_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            reasoning_estimated=self.reasoning_estimated or other.reasoning_estimated,
        )


class ChatResponse(BaseModel):
    """Normalized chat response.

    `text` has any think/reasoning blocks stripped.
    `raw_text` is the unstripped concatenation, useful for thinking auto-detection.
    `reasoning_text` collects separated reasoning content.
    """

    model_config = ConfigDict(extra="ignore")

    text: str
    raw_text: str = ""
    reasoning_text: str = ""
    finish_reason: str = "stop"
    usage: Usage = Field(default_factory=Usage)
    latency_ms: float = 0.0
    provider_request_id: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    thinking_observed: bool = False
    cache_hit: bool = False


class ModelInfo(BaseModel):
    """Subset of `/v1/models` response we care about."""

    model_config = ConfigDict(extra="ignore")

    id: str
    owned_by: str | None = None
    created: int | None = None
