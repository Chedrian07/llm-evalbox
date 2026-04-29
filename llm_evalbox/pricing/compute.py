# SPDX-License-Identifier: Apache-2.0
"""Cost estimation. Always estimated — flagged in result.json."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from llm_evalbox.core.request import Usage

logger = logging.getLogger(__name__)

CATALOG_PATH = Path(__file__).parent / "catalog.yaml"


@dataclass
class PriceOverrides:
    """User-specified prices override the catalog match (per-million-token, USD)."""

    input: float | None = None
    cached_input: float | None = None
    output: float | None = None
    reasoning: float | None = None


@dataclass
class Price:
    input: float
    cached_input: float
    output: float
    reasoning: float


_CATALOG_CACHE: list[tuple[re.Pattern[str], Price]] | None = None


def _load_catalog() -> list[tuple[re.Pattern[str], Price]]:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is None:
        _CATALOG_CACHE = []
        if not CATALOG_PATH.exists():
            return _CATALOG_CACHE
        with open(CATALOG_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for entry in data.get("models", []) or []:
            pat = entry.get("pattern")
            if not pat:
                continue
            try:
                rx = re.compile(pat, re.IGNORECASE)
            except re.error as e:
                logger.warning("invalid pricing pattern %r: %s", pat, e)
                continue
            _CATALOG_CACHE.append(
                (
                    rx,
                    Price(
                        input=float(entry.get("input") or 0.0),
                        cached_input=float(entry.get("cached_input") or entry.get("input") or 0.0),
                        output=float(entry.get("output") or 0.0),
                        reasoning=float(entry.get("reasoning") or entry.get("output") or 0.0),
                    ),
                )
            )
    return _CATALOG_CACHE


def lookup_price(model: str) -> Price | None:
    """Return the first matching catalog entry, or None."""
    for rx, price in _load_catalog():
        if rx.search(model):
            return price
    return None


def _resolve(model: str, ov: PriceOverrides | None) -> Price | None:
    base = lookup_price(model)
    if ov is None:
        return base
    if base is None and not any(getattr(ov, k) is not None for k in ("input", "cached_input", "output", "reasoning")):
        return None
    base = base or Price(0.0, 0.0, 0.0, 0.0)
    return Price(
        input=ov.input if ov.input is not None else base.input,
        cached_input=ov.cached_input if ov.cached_input is not None else base.cached_input,
        output=ov.output if ov.output is not None else base.output,
        reasoning=ov.reasoning if ov.reasoning is not None else base.reasoning,
    )


def cost_for_usage(
    model: str,
    usage: Usage,
    *,
    overrides: PriceOverrides | None = None,
) -> float | None:
    """USD cost estimate. Returns None when no catalog/override price is available."""
    price = _resolve(model, overrides)
    if price is None:
        return None
    # cached_prompt_tokens is a *subset* of prompt_tokens reported by some providers;
    # we treat it as billed at the cached rate and the remainder at full input rate.
    prompt = max(0, usage.prompt_tokens - usage.cached_prompt_tokens)
    cached = usage.cached_prompt_tokens
    output = max(0, usage.completion_tokens - usage.reasoning_tokens)
    reasoning = usage.reasoning_tokens
    cost = (
        prompt * price.input
        + cached * price.cached_input
        + output * price.output
        + reasoning * price.reasoning
    ) / 1_000_000.0
    return round(cost, 6)
