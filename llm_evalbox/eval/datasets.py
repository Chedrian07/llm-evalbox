# SPDX-License-Identifier: Apache-2.0
"""Dataset loading: bundled JSONL → cache fallback + sha256 verify + deterministic sampling.

`SAMPLE_SEED=42` is shared with OMLX; same setting → same questions across
models, regardless of provider.

Resolution order for each file:
  1. Bundled — `llm_evalbox/data/datasets/<file>` (shipped with the wheel).
  2. Override dir — `$EVALBOX_DATASETS_DIR/<bench>/<file>` if set.
  3. Cache dir — `~/.cache/llm-evalbox/datasets/<bench>/<file>` (downloaded on first use).

When a manifest entry has `bundled: true`, network fetch is never attempted
and a clear error is raised if the bundled file is missing (likely a packaging
bug). Otherwise we fall through to cache + lazy fetch.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import shutil
from pathlib import Path
from typing import Any

import httpx
import yaml

from llm_evalbox.core.exceptions import DatasetError

logger = logging.getLogger(__name__)

SAMPLE_SEED = 42

DATA_DIR = Path(__file__).parent.parent / "data"
MANIFEST_PATH = DATA_DIR / "manifest.yaml"
BUNDLED_DIR = DATA_DIR / "datasets"


# --------------------------------------------------------------------- paths
def datasets_dir() -> Path:
    """Resolve the datasets cache dir.

    Priority: $EVALBOX_DATASETS_DIR > $EVALBOX_CACHE_DIR/datasets > ~/.cache/llm-evalbox/datasets.
    """
    explicit = os.environ.get("EVALBOX_DATASETS_DIR")
    if explicit:
        return Path(explicit).expanduser()
    cache = os.environ.get("EVALBOX_CACHE_DIR")
    if cache:
        return Path(cache).expanduser() / "datasets"
    return Path("~/.cache/llm-evalbox/datasets").expanduser()


# ----------------------------------------------------------------- jsonl I/O
def load_jsonl(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise DatasetError(f"{path}:{ln}: invalid JSON: {e}") from e
    return items


# -------------------------------------------------------------------- sample
def deterministic_sample(items: list[dict], n: int) -> list[dict]:
    if n <= 0 or n >= len(items):
        return list(items)
    rng = random.Random(SAMPLE_SEED)
    return rng.sample(items, n)


def stratified_sample(items: list[dict], n: int, key: str) -> list[dict]:
    """Proportional sample by `key`. Falls back to deterministic if key missing."""
    if n <= 0 or n >= len(items):
        return list(items)
    rng = random.Random(SAMPLE_SEED)
    groups: dict[str, list[dict]] = {}
    for it in items:
        groups.setdefault(str(it.get(key, "_unknown")), []).append(it)

    total = len(items)
    out: list[dict] = []
    remaining = n
    cats = sorted(groups.keys())
    for i, c in enumerate(cats):
        g = groups[c]
        if i == len(cats) - 1:
            count = remaining
        else:
            count = max(1, round(len(g) / total * n))
            count = min(count, remaining, len(g))
        out.extend(rng.sample(g, min(count, len(g))))
        remaining -= count
        if remaining <= 0:
            break
    return out[:n]


# ----------------------------------------------------------------- manifest
_MANIFEST_CACHE: dict[str, dict[str, Any]] | None = None


def load_manifest() -> dict[str, dict[str, Any]]:
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is None:
        if not MANIFEST_PATH.exists():
            raise DatasetError(f"manifest missing: {MANIFEST_PATH}")
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            _MANIFEST_CACHE = yaml.safe_load(f) or {}
    return _MANIFEST_CACHE


# ----------------------------------------------------------------- sha + dl
def _sha256_of(path: Path, *, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _download(url: str, dest: Path, *, expected_sha: str | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    logger.info("download %s → %s", url, dest)
    with httpx.stream("GET", url, follow_redirects=True, timeout=300.0) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    if expected_sha:
        got = _sha256_of(tmp)
        if got.lower() != expected_sha.lower():
            tmp.unlink(missing_ok=True)
            raise DatasetError(
                f"sha256 mismatch for {url}: expected {expected_sha}, got {got}"
            )
    shutil.move(str(tmp), dest)


def ensure_dataset(name: str) -> dict[str, Path]:
    """Return {file_name: local_path} for the named dataset.

    Resolution per file:
      1. Bundled in `llm_evalbox/data/datasets/` (shipped with wheel) — used directly.
      2. Cached at `datasets_dir()/<name>/<file>` — used directly if present.
      3. Manifest URL — downloaded into the cache (if URL is set).
    """
    manifest = load_manifest()
    if name not in manifest:
        raise DatasetError(f"unknown dataset {name!r} (not in manifest)")
    spec = manifest[name]
    files = spec.get("files") or []
    if not files:
        raise DatasetError(f"dataset {name!r} has no files in manifest")

    bundled_only = bool(spec.get("bundled"))
    base = datasets_dir() / name
    out: dict[str, Path] = {}
    for f in files:
        fname = f["name"]
        url = f.get("url") or ""
        sha = f.get("sha256") or ""

        bundled_path = BUNDLED_DIR / fname
        if bundled_path.exists():
            out[fname] = bundled_path
            continue

        local = base / fname
        if local.exists():
            out[fname] = local
            continue

        if bundled_only or not url:
            raise DatasetError(
                f"dataset {name!r} file {fname!r} is missing. "
                f"Expected bundled at {bundled_path} or cached at {local}."
            )

        try:
            _download(url, local, expected_sha=sha)
        except httpx.HTTPError as e:
            raise DatasetError(f"failed to fetch {url}: {e}") from e
        out[fname] = local
    return out
