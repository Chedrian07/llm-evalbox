# SPDX-License-Identifier: Apache-2.0
"""Exception hierarchy.

The orchestrator and CLI catch only EvalBoxError subclasses, so adapters
should wrap underlying httpx errors before raising.
"""


class EvalBoxError(Exception):
    """Base for all evalbox-raised errors."""


class AdapterError(EvalBoxError):
    """Raised by provider adapters when a call fails non-recoverably."""

    def __init__(self, message: str, *, status_code: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class AuthError(AdapterError):
    """401 / 403."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, status_code=status_code, retryable=False)


class BadRequestError(AdapterError):
    """400 — malformed request, unsupported parameter, etc."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, status_code=status_code, retryable=False)


class RateLimitError(AdapterError):
    """429 — caller should back off."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message, status_code=429, retryable=True)
        self.retry_after = retry_after


class NetworkError(AdapterError):
    """Connection / timeout / 5xx."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, status_code=status_code, retryable=True)


class DatasetError(EvalBoxError):
    """Raised on dataset download / sha256 mismatch / parse failure."""


class SandboxError(EvalBoxError):
    """Raised on code-execution sandbox failures (configuration / policy)."""


class ConfigError(EvalBoxError):
    """Raised on invalid CLI flags / .env / profile."""
