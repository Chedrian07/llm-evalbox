# SPDX-License-Identifier: Apache-2.0
"""Provider adapters. Chat Completions is M0; Responses is M2."""

from llm_evalbox.adapters.auto import resolve_adapter
from llm_evalbox.adapters.base import ChatAdapter
from llm_evalbox.adapters.capabilities import (
    Capability,
    capability_for,
    strip_unsupported_keys,
)
from llm_evalbox.adapters.chat_completions import ChatCompletionsAdapter
from llm_evalbox.adapters.ratelimit import RateLimiter
from llm_evalbox.adapters.retry import retry_policy

__all__ = [
    "Capability",
    "ChatAdapter",
    "ChatCompletionsAdapter",
    "RateLimiter",
    "capability_for",
    "resolve_adapter",
    "retry_policy",
    "strip_unsupported_keys",
]
