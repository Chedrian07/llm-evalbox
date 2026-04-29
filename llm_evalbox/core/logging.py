# SPDX-License-Identifier: Apache-2.0
"""Logger helpers — module loggers + truncated-body formatting."""

import logging
import os


def setup_logging(level: str | None = None) -> None:
    """Configure root logger once. Level priority: arg > env > default WARNING."""
    if level is None:
        level = os.environ.get("EVALBOX_LOG_LEVEL", "WARNING")
    level = level.upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.WARNING),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def truncate(s: str, n: int = 1024) -> str:
    """Truncate a string for logging, preserving readability."""
    if len(s) <= n:
        return s
    return s[:n] + f"... [+{len(s) - n} bytes]"
