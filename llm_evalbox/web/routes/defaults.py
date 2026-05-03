# SPDX-License-Identifier: Apache-2.0
"""GET /api/defaults — surface .env / process-env defaults to the SPA.

The SPA hydrates its store from this endpoint so values set via
`evalbox web` (with .env loaded) show up in the connection / options
inputs immediately, instead of always rendering the OpenAI public
defaults.

We deliberately do NOT echo the API key — the SPA leaves the key field
blank and the existing `POST /api/connection/test` / `POST /api/runs`
routes resolve it server-side via `resolve_api_key(api_key_env)`.
The response includes `has_api_key` so the UI can show a "key picked
up from $X" hint.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter

from llm_evalbox.adapters.auth import resolve_api_key

router = APIRouter()

_API_KEY_ENV_CANDIDATES = (
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "TOGETHER_API_KEY",
    "FIREWORKS_API_KEY",
    "VLLM_KEY",
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "E2B_API_KEY",
)


def _str_env(name: str) -> str | None:
    v = os.environ.get(name)
    return v if v else None


def _int_env(name: str) -> int | None:
    v = os.environ.get(name)
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _float_env(name: str) -> float | None:
    v = os.environ.get(name)
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _bool_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


@router.get("/api/defaults")
def get_defaults() -> dict[str, Any]:
    detected_keys: list[str] = []
    for name in _API_KEY_ENV_CANDIDATES:
        if os.environ.get(name):
            detected_keys.append(name)

    primary_env = detected_keys[0] if detected_keys else "OPENAI_API_KEY"
    has_api_key = resolve_api_key(primary_env) is not None

    return {
        "base_url": _str_env("EVALBOX_BASE_URL"),
        "model": _str_env("EVALBOX_MODEL"),
        "adapter": _str_env("EVALBOX_ADAPTER"),
        "thinking": _str_env("EVALBOX_THINKING"),
        "concurrency": _int_env("EVALBOX_CONCURRENCY"),
        "rpm": _int_env("EVALBOX_RPM"),
        "tpm": _int_env("EVALBOX_TPM"),
        "max_cost_usd": _float_env("EVALBOX_MAX_COST_USD"),
        "accept_code_exec": _bool_env("EVALBOX_ACCEPT_CODE_EXEC"),
        "no_cache": _bool_env("EVALBOX_NO_CACHE"),
        "drop_params": _str_env("EVALBOX_DROP_PARAMS"),
        # API key info — never the value itself.
        "api_key_env": primary_env,
        "has_api_key": has_api_key,
        "detected_api_key_envs": detected_keys,
    }
