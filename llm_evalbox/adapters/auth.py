# SPDX-License-Identifier: Apache-2.0
"""API key resolution. Keys live only in process memory; never echoed to clients."""

import logging
import os

logger = logging.getLogger(__name__)


def resolve_api_key(env_var: str | None, explicit: str | None = None) -> str | None:
    """Return the key, preferring explicit > env_var > common fallbacks."""
    if explicit:
        return explicit
    if env_var:
        v = os.environ.get(env_var)
        if v:
            return v
        logger.debug("api key env var %r is unset", env_var)
    for fallback in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "TOGETHER_API_KEY"):
        v = os.environ.get(fallback)
        if v:
            logger.debug("using fallback api key from %s", fallback)
            return v
    return None
