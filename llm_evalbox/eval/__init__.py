# SPDX-License-Identifier: Apache-2.0
"""Benchmark registry. Add new benchmarks here."""

from llm_evalbox.eval.base import (
    BaseBenchmark,
    BenchmarkResult,
    QuestionResult,
    SamplingOverrides,
)
from llm_evalbox.eval.gsm8k import GSM8KBenchmark
from llm_evalbox.eval.hellaswag import HellaSwagBenchmark
from llm_evalbox.eval.humaneval import HumanEvalBenchmark
from llm_evalbox.eval.mmlu import MMLUBenchmark
from llm_evalbox.eval.truthfulqa import TruthfulQABenchmark

BENCHMARKS: dict[str, type[BaseBenchmark]] = {
    "mmlu": MMLUBenchmark,
    "gsm8k": GSM8KBenchmark,
    "humaneval": HumanEvalBenchmark,
    "truthfulqa": TruthfulQABenchmark,
    "hellaswag": HellaSwagBenchmark,
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
