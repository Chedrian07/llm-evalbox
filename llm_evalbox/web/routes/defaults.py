# SPDX-License-Identifier: Apache-2.0
"""GET /api/defaults — surface .env / process-env defaults to the SPA.

The SPA hydrates its store from this endpoint so values set via
`evalbox web` (with .env loaded) show up in the connection / options
inputs immediately, instead of always rendering the OpenAI public
defaults.

We deliberately do NOT echo the API key — the SPA leaves the key field
blank and the existing `POST /api/connection/test` / `POST /api/runs`
routes resolve it server-side via `resolve_api_key(api_key_env)`.
The response includes `has_api_key` (for the primary env) plus an
`api_keys` dict so the UI can correctly reflect availability when the
user picks a different `api_key_env`.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter

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
    if v is None:
        return None
    v = v.strip()
    return v if v else None


def _int_env(name: str) -> int | None:
    v = _str_env(name)
    if v is None:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _float_env(name: str) -> float | None:
    v = _str_env(name)
    if v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _bool_env(name: str) -> bool:
    v = _str_env(name)
    return v is not None and v.lower() in ("1", "true", "yes", "on")


@router.get("/api/defaults")
def get_defaults() -> dict[str, Any]:
    # Direct os.environ lookup — `resolve_api_key` falls back across common
    # candidates (OPENAI/OPENROUTER/TOGETHER) which makes per-env presence
    # bleed over and tells the SPA "OPENAI_API_KEY is set" when only
    # OPENROUTER_API_KEY actually is.
    detected_keys: list[str] = []
    api_keys: dict[str, bool] = {}
    for name in _API_KEY_ENV_CANDIDATES:
        present = bool((os.environ.get(name) or "").strip())
        api_keys[name] = present
        if present:
            detected_keys.append(name)

    primary_env = detected_keys[0] if detected_keys else "OPENAI_API_KEY"

    return {
        # Core connection
        "base_url": _str_env("EVALBOX_BASE_URL"),
        "model": _str_env("EVALBOX_MODEL"),
        "adapter": _str_env("EVALBOX_ADAPTER"),
        "profile": _str_env("EVALBOX_PROFILE"),
        # Run / sampling knobs
        "thinking": _str_env("EVALBOX_THINKING"),
        "reasoning_effort": _str_env("EVALBOX_REASONING_EFFORT"),
        "concurrency": _int_env("EVALBOX_CONCURRENCY"),
        "rpm": _int_env("EVALBOX_RPM"),
        "tpm": _int_env("EVALBOX_TPM"),
        "max_cost_usd": _float_env("EVALBOX_MAX_COST_USD"),
        # Boolean toggles
        "accept_code_exec": _bool_env("EVALBOX_ACCEPT_CODE_EXEC"),
        "no_cache": _bool_env("EVALBOX_NO_CACHE"),
        "strict_failures": _bool_env("EVALBOX_STRICT_FAILURES"),
        "no_thinking_rerun": _bool_env("EVALBOX_NO_THINKING_RERUN"),
        "prompt_cache_aware": _bool_env("EVALBOX_PROMPT_CACHE_AWARE"),
        # Capability override
        "drop_params": _str_env("EVALBOX_DROP_PARAMS"),
        # API key info — never the value itself.
        "api_key_env": primary_env,
        "has_api_key": api_keys.get(primary_env, False),
        "detected_api_key_envs": detected_keys,
        "api_keys": api_keys,
    }
