# SPDX-License-Identifier: Apache-2.0
"""Adapter resolution: auto / chat_completions / responses.

`auto` is treated as `chat_completions` (the broadest-compatible default —
vLLM/SGLang/Ollama/OpenRouter/Together/Fireworks all expose this route).
Responses is opt-in: pass `--adapter responses` or set
`EVALBOX_ADAPTER=responses` when targeting OpenAI's o-series / gpt-5.

There is no automatic probe between the two — gateways rarely expose
`/v1/responses`, so a probe round-trip would be wasteful. See `docs/adapters.md`.
"""

from __future__ import annotations

import logging

from llm_evalbox.adapters.base import ChatAdapter
from llm_evalbox.adapters.chat_completions import ChatCompletionsAdapter
from llm_evalbox.adapters.responses import ResponsesAdapter
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
      - `auto` (default) | `chat` | `chat_completions` → ChatCompletionsAdapter
      - `responses` → ResponsesAdapter (`/v1/responses`)
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
        return ResponsesAdapter(
            base_url=base_url,
            api_key=api_key,
            extra_headers=extra_headers,
            timeout=timeout,
        )
    raise ConfigError(f"unknown adapter kind: {kind!r}")
