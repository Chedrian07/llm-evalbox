# SPDX-License-Identifier: Apache-2.0
"""tenacity retry policy for adapter HTTP calls.

Retries network errors, timeouts, and 408/425/429/5xx. 4xx auth/bad-request
raise immediately. Honors `Retry-After` for 429.
"""

from __future__ import annotations

import logging

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from llm_evalbox.core.exceptions import NetworkError, RateLimitError

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504, 529})


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, NetworkError):
        return True
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.NetworkError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS
    return False


def retry_policy(max_attempts: int = 6) -> AsyncRetrying:
    return AsyncRetrying(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(initial=1.0, max=60.0),
        reraise=True,
    )
