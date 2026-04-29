# SPDX-License-Identifier: Apache-2.0
"""ChatAdapter ABC.

Concrete adapters: chat_completions (M0), responses (M2 stub).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from llm_evalbox.core.request import ChatRequest, ChatResponse, ModelInfo


class ChatAdapter(ABC):
    name: str = "abstract"
    base_url: str = ""
    api_key: str | None = None

    @abstractmethod
    async def chat(self, req: ChatRequest) -> ChatResponse:
        """Run one normalized chat request."""

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """Return available models. Empty list if endpoint doesn't expose `/v1/models`."""

    def supports(self, feature: str) -> bool:
        """Coarse capability hint. Adapters override if needed."""
        return False

    async def close(self) -> None:
        """Close any underlying clients/sessions."""

    async def __aenter__(self) -> ChatAdapter:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
