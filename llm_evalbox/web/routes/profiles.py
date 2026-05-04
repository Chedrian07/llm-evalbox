# SPDX-License-Identifier: Apache-2.0
"""/api/profiles — CRUD over the SQLite-backed connection profiles.

Profiles are keyed by `name` and store a connection bundle the user
can switch between with one click in the SPA's ConnectionCard.
Write paths happen exclusively here (and `evalbox profiles save` once
that CLI exists); the legacy TOML file is read-only after the one-shot
import.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from llm_evalbox.cache import profiles_db

router = APIRouter()


class ProfilePayload(BaseModel):
    name: str = Field(..., min_length=1)
    base_url: str | None = None
    model: str | None = None
    adapter: str | None = "auto"
    api_key_env: str | None = None
    extra_headers: dict[str, str] = Field(default_factory=dict)
    sampling: dict[str, Any] = Field(default_factory=dict)


@router.get("/api/profiles")
def list_profiles() -> list[dict]:
    return profiles_db.list_profiles()


@router.get("/api/profiles/{name}")
def get_profile(name: str) -> dict:
    row = profiles_db.load_profile_db(name)
    if row is None:
        raise HTTPException(status_code=404, detail="profile not found")
    return row


@router.post("/api/profiles")
def upsert_profile(payload: ProfilePayload) -> dict:
    """Create or fully replace a profile. Returns the canonical row.
    Body fields not supplied default to None / empty dicts (i.e. the
    profile is the union of what's in the body)."""
    try:
        return profiles_db.save_profile(
            payload.name,
            base_url=payload.base_url,
            model=payload.model,
            adapter=payload.adapter,
            api_key_env=payload.api_key_env,
            extra_headers=payload.extra_headers,
            sampling=payload.sampling,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/api/profiles/{name}")
def delete_profile(name: str) -> dict[str, bool]:
    if not profiles_db.delete_profile(name):
        raise HTTPException(status_code=404, detail="profile not found")
    return {"deleted": True}


@router.post("/api/profiles/{name}/use")
def use_profile(name: str) -> dict:
    """Bump `last_used_at` and return the row so the SPA can hydrate
    its ConnectionCard from the response without a separate GET."""
    row = profiles_db.touch_last_used(name)
    if row is None:
        raise HTTPException(status_code=404, detail="profile not found")
    return row
