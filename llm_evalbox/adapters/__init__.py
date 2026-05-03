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
from llm_evalbox.adapters.learned import (
    clear as clear_learned,
)
from llm_evalbox.adapters.learned import (
    forget as forget_learned,
)
from llm_evalbox.adapters.learned import (
    list_all as list_learned,
)
from llm_evalbox.adapters.learned import (
    lookup as lookup_learned,
)
from llm_evalbox.adapters.learned import (
    remember as remember_learned,
)
from llm_evalbox.adapters.ratelimit import RateLimiter
from llm_evalbox.adapters.responses import ResponsesAdapter
from llm_evalbox.adapters.retry import retry_policy

__all__ = [
    "Capability",
    "ChatAdapter",
    "ChatCompletionsAdapter",
    "RateLimiter",
    "ResponsesAdapter",
    "capability_for",
    "clear_learned",
    "forget_learned",
    "list_learned",
    "lookup_learned",
    "remember_learned",
    "resolve_adapter",
    "retry_policy",
    "strip_unsupported_keys",
]
