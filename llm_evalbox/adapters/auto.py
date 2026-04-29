# SPDX-License-Identifier: Apache-2.0
"""Adapter resolution: auto / chat_completions / responses (M2).

For M0 we always return the chat-completions adapter; the auto-detection
for Responses lives in M2 (`responses.py`).
"""

from __future__ import annotations

import logging

from llm_evalbox.adapters.base import ChatAdapter
from llm_evalbox.adapters.chat_completions import ChatCompletionsAdapter
from llm_evalbox.core.exceptions import ConfigError

logger = logging.getLogger(__name__)


def resolve_adapter(
    *,
    kind: str,
    base_url: str,
    api_key: str | None,
    extra_headers: dict[str, str] | None = None,
    timeout: float = 120.0,
) -> ChatAdapter:
    """Return a concrete ChatAdapter based on `kind`.

    `kind`:
      - "chat_completions" or "chat" → /v1/chat/completions
      - "responses" → /v1/responses (M2; raises until implemented)
      - "auto" → for M0, treats as chat_completions. M2 will dry-call to decide.
    """
    k = (kind or "auto").lower()
    if k in ("auto", "chat", "chat_completions"):
        return ChatCompletionsAdapter(
            base_url=base_url,
            api_key=api_key,
            extra_headers=extra_headers,
            timeout=timeout,
        )
    if k == "responses":
        raise ConfigError(
            "responses adapter is not implemented yet (M2). Use --adapter chat or auto."
        )
    raise ConfigError(f"unknown adapter kind: {kind!r}")
