# SPDX-License-Identifier: Apache-2.0
"""Core normalized DTOs shared by adapters and benchmarks."""

from llm_evalbox.core.exceptions import (
    AdapterError,
    AuthError,
    BadRequestError,
    EvalBoxError,
    NetworkError,
    RateLimitError,
)
from llm_evalbox.core.messages import Message
from llm_evalbox.core.request import ChatRequest, ChatResponse, ModelInfo, Usage
from llm_evalbox.core.thinking import (
    ThinkingMode,
    apply_thinking_to_request,
    parse_thinking,
    thinking_token_budget,
)

__all__ = [
    "AdapterError",
    "AuthError",
    "BadRequestError",
    "ChatRequest",
    "ChatResponse",
    "EvalBoxError",
    "Message",
    "ModelInfo",
    "NetworkError",
    "RateLimitError",
    "ThinkingMode",
    "Usage",
    "apply_thinking_to_request",
    "parse_thinking",
    "thinking_token_budget",
]
