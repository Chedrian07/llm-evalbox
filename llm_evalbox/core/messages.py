# SPDX-License-Identifier: Apache-2.0
"""Message DTO — the single chat-message representation across adapters."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

Role = Literal["system", "user", "assistant", "tool"]


class Message(BaseModel):
    """One chat-completions style message.

    Adapters convert to provider-specific shapes (Responses input items, etc.).
    """

    model_config = ConfigDict(extra="ignore")

    role: Role
    content: str
