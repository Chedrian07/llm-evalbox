# SPDX-License-Identifier: Apache-2.0
"""GET /api/benchmarks — registry metadata for the Setup page."""

from __future__ import annotations

from fastapi import APIRouter

from llm_evalbox.eval import BENCHMARKS
from llm_evalbox.eval.datasets import load_manifest
from llm_evalbox.web.schemas import BenchmarkInfo

router = APIRouter()


# Hand-curated category map. Keep aligned with BENCHMARKS in eval/__init__.py.
_CATEGORIES: dict[str, str] = {
    "mmlu": "knowledge",
    "mmlu_pro": "knowledge",
    "arc_challenge": "knowledge",
    "hellaswag": "reasoning",
    "winogrande": "reasoning",
    "gsm8k": "math",
    "mathqa": "math",
    "humaneval": "coding",
    "mbpp": "coding",
    "livecodebench": "coding",
    "truthfulqa": "truthful",
    "kmmlu": "multilingual",
    "cmmlu": "multilingual",
    "jmmlu": "multilingual",
    "bbq": "safety",
    "safetybench": "safety",
}


@router.get("/api/benchmarks", response_model=list[BenchmarkInfo])
def list_benchmarks() -> list[BenchmarkInfo]:
    manifest = load_manifest()
    out: list[BenchmarkInfo] = []
    for name, cls in sorted(BENCHMARKS.items()):
        b = cls()
        # Manifest key is keyed by dataset_key; for most benches the
        # registry name matches. KMMLU/CMMLU/JMMLU also align.
        meta = manifest.get(name) or {}
        out.append(BenchmarkInfo(
            name=name,
            quick_size=b.quick_size,
            is_code_bench=b.is_code_bench(),
            category=_CATEGORIES.get(name, "other"),
            license=meta.get("license"),
        ))
    return out
