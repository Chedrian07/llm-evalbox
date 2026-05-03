# SPDX-License-Identifier: Apache-2.0
"""POST /api/pricing/estimate — rough cost / time forecast for a planned run."""

from __future__ import annotations

from fastapi import APIRouter

from llm_evalbox.core.request import Usage
from llm_evalbox.eval import BENCHMARKS, get_benchmark
from llm_evalbox.pricing import cost_for_usage
from llm_evalbox.web.schemas import PricingEstimateRequest, PricingEstimateResponse

router = APIRouter()


# Crude per-bench averages — used purely to give the user a "this run will be
# roughly $X" preview before they hit Run. The actual run reports exact tokens.
_AVG_PROMPT_TOKENS = {
    "mmlu": 800, "mmlu_pro": 900, "arc_challenge": 250,
    "hellaswag": 400, "winogrande": 200,
    "gsm8k": 600, "mathqa": 300,
    "humaneval": 350, "mbpp": 250, "livecodebench": 600,
    "truthfulqa": 300,
    "kmmlu": 600, "cmmlu": 600, "jmmlu": 600,
    "bbq": 400, "safetybench": 200,
}
_AVG_COMPLETION_TOKENS = {
    "mmlu": 5, "mmlu_pro": 6, "arc_challenge": 5, "hellaswag": 5, "winogrande": 5,
    "gsm8k": 200, "mathqa": 150,
    "humaneval": 700, "mbpp": 700, "livecodebench": 1500,
    "truthfulqa": 5,
    "kmmlu": 5, "cmmlu": 5, "jmmlu": 5,
    "bbq": 5, "safetybench": 5,
}


@router.post("/api/pricing/estimate", response_model=PricingEstimateResponse)
def estimate(req: PricingEstimateRequest) -> PricingEstimateResponse:
    total_prompt = 0
    total_completion = 0
    total_reasoning = 0
    total_seconds = 0
    for name in req.benchmarks:
        if name not in BENCHMARKS:
            continue
        bench = get_benchmark(name)
        n = req.samples if req.samples > 0 else bench.quick_size
        ap = _AVG_PROMPT_TOKENS.get(name, 500)
        ac = _AVG_COMPLETION_TOKENS.get(name, 50)
        total_prompt += ap * n
        total_completion += ac * n
        # If thinking is on/auto, assume reasoning ~= completion as a coarse
        # placeholder. The real run captures the right number.
        if req.thinking != "off":
            total_reasoning += ac * n * 4
        # ~5s per question at concurrency=8 ≈ n / 8 * 5
        total_seconds += int(n / 8 * 5)

    usage = Usage(
        prompt_tokens=total_prompt,
        completion_tokens=total_completion,
        reasoning_tokens=total_reasoning,
        total_tokens=total_prompt + total_completion + total_reasoning,
    )
    cost = cost_for_usage(req.model, usage)

    return PricingEstimateResponse(
        est_prompt_tokens=total_prompt,
        est_completion_tokens=total_completion,
        est_reasoning_tokens=total_reasoning,
        est_cost_usd=cost,
        est_seconds=total_seconds,
    )
