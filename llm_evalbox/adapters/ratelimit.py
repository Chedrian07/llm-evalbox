# SPDX-License-Identifier: Apache-2.0
"""Token-bucket rate limiter for RPM and TPM, plus an asyncio.Semaphore for concurrency.

Tokens (TPM) are pessimistically estimated from `len(text)//3` if tiktoken is
absent — close enough to keep us out of provider rate limits for benchmarking.
"""

from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class _Bucket:
    """Simple async token bucket. capacity = burst, refill_rate per second."""

    def __init__(self, capacity: float, refill_per_sec: float):
        self.capacity = float(capacity)
        self.refill = float(refill_per_sec)
        self.tokens = float(capacity)
        self.last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, n: float) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.refill)
                self.last = now
                if self.tokens >= n:
                    self.tokens -= n
                    return
                deficit = n - self.tokens
                wait_s = deficit / self.refill if self.refill > 0 else 60.0
                logger.debug("ratelimit wait %.2fs (need %.0f, have %.1f)", wait_s, n, self.tokens)
                await asyncio.sleep(min(wait_s, 5.0))


class RateLimiter:
    """RPM + TPM + concurrency. Any of the three can be None to disable that gate."""

    def __init__(
        self,
        *,
        rpm: int | None = None,
        tpm: int | None = None,
        concurrency: int = 8,
    ):
        self.rpm = rpm
        self.tpm = tpm
        self._req_bucket = _Bucket(rpm, rpm / 60.0) if rpm else None
        self._tok_bucket = _Bucket(tpm, tpm / 60.0) if tpm else None
        self._sem = asyncio.Semaphore(concurrency)

    async def acquire(self, est_tokens: int = 0) -> None:
        await self._sem.acquire()
        if self._req_bucket:
            await self._req_bucket.acquire(1)
        if self._tok_bucket and est_tokens > 0:
            await self._tok_bucket.acquire(est_tokens)

    def release(self) -> None:
        self._sem.release()

    async def __aenter__(self) -> RateLimiter:
        await self.acquire()
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.release()


def estimate_tokens(text: str) -> int:
    """Cheap upper-bound estimator (no tiktoken)."""
    return max(1, len(text) // 3)
