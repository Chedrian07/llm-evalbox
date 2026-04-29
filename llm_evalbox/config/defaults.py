# SPDX-License-Identifier: Apache-2.0
"""Hard-coded defaults — the lowest layer of the priority stack."""

from __future__ import annotations

DEFAULTS: dict[str, object] = {
    "adapter": "auto",
    "concurrency": 8,
    "sandbox_workers": 4,
    "thinking": "auto",
    "samples": 200,
    "seed": 42,
    "sandbox": "subprocess",
    "web_host": "127.0.0.1",
    "web_port": 8765,
    "web_open_browser": True,
    "max_attempts": 6,
    "timeout_s": 120.0,
    "api_key_env": "OPENAI_API_KEY",
}
