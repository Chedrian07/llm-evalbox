# SPDX-License-Identifier: Apache-2.0
"""Benchmark registry. Add new benchmarks here."""

from llm_evalbox.eval.arc import ARCChallengeBenchmark
from llm_evalbox.eval.base import (
    BaseBenchmark,
    BenchmarkResult,
    QuestionResult,
    SamplingOverrides,
)
from llm_evalbox.eval.bbq import BBQBenchmark
from llm_evalbox.eval.gsm8k import GSM8KBenchmark
from llm_evalbox.eval.hellaswag import HellaSwagBenchmark
from llm_evalbox.eval.humaneval import HumanEvalBenchmark
from llm_evalbox.eval.livecodebench import LiveCodeBenchBenchmark
from llm_evalbox.eval.mathqa import MathQABenchmark
from llm_evalbox.eval.mbpp import MBPPBenchmark
from llm_evalbox.eval.mmlu import MMLUBenchmark
from llm_evalbox.eval.mmlu_pro import MMLUProBenchmark
from llm_evalbox.eval.multilingual_mmlu import (
    CMMLUBenchmark,
    JMMLUBenchmark,
    KMMLUBenchmark,
)
from llm_evalbox.eval.safetybench import SafetyBenchBenchmark
from llm_evalbox.eval.truthfulqa import TruthfulQABenchmark
from llm_evalbox.eval.winogrande import WinograndeBenchmark

BENCHMARKS: dict[str, type[BaseBenchmark]] = {
    # Knowledge MC
    "mmlu": MMLUBenchmark,
    "mmlu_pro": MMLUProBenchmark,
    "arc_challenge": ARCChallengeBenchmark,
    # Reasoning / commonsense
    "hellaswag": HellaSwagBenchmark,
    "winogrande": WinograndeBenchmark,
    # Math
    "gsm8k": GSM8KBenchmark,
    "mathqa": MathQABenchmark,
    # Coding (sandbox tier1, opt-in)
    "humaneval": HumanEvalBenchmark,
    "mbpp": MBPPBenchmark,
    "livecodebench": LiveCodeBenchBenchmark,
    # Truthfulness
    "truthfulqa": TruthfulQABenchmark,
    # Multilingual MMLU
    "kmmlu": KMMLUBenchmark,
    "cmmlu": CMMLUBenchmark,
    "jmmlu": JMMLUBenchmark,
    # Safety / fairness
    "bbq": BBQBenchmark,
    "safetybench": SafetyBenchBenchmark,
}


def get_benchmark(name: str) -> BaseBenchmark:
    if name not in BENCHMARKS:
        raise KeyError(f"unknown benchmark {name!r}; available: {sorted(BENCHMARKS)}")
    return BENCHMARKS[name]()


__all__ = [
    "BENCHMARKS",
    "BaseBenchmark",
    "BenchmarkResult",
    "QuestionResult",
    "SamplingOverrides",
    "get_benchmark",
]
