# SPDX-License-Identifier: Apache-2.0
"""Rich-table renderer for CLI summary."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from llm_evalbox.eval.base import BenchmarkResult


def _fmt_lat(ms: float) -> str:
    if ms == 0:
        return "—"
    if ms >= 1000:
        return f"{ms/1000:.2f}s"
    return f"{ms:.0f}ms"


def render_run_table(
    results: list[BenchmarkResult],
    *,
    costs: dict[str, float | None] | None = None,
    console: Console | None = None,
) -> None:
    """Print one row per benchmark plus a totals footer.

    `costs[bench_name]` is the per-bench USD estimate; pass None when the
    catalog had no match for the model (the column will show "—").
    """
    console = console or Console()
    costs = costs or {}

    table = Table(title="evalbox results", show_lines=False)
    table.add_column("benchmark", style="bold")
    table.add_column("samples", justify="right")
    table.add_column("accuracy", justify="right")
    table.add_column("CI95", justify="right")
    table.add_column("p50", justify="right")
    table.add_column("p95", justify="right")
    table.add_column("prompt", justify="right")
    table.add_column("compl.", justify="right")
    table.add_column("reason.", justify="right")
    table.add_column("cost USD", justify="right")

    total_prompt = total_compl = total_reason = 0
    total_cost: float = 0.0
    has_cost = False
    n_correct = 0
    n_scored = 0

    for r in results:
        cost = costs.get(r.benchmark_name)
        cost_str = f"{cost:.4f}" if cost is not None else "—"
        if cost is not None:
            total_cost += cost
            has_cost = True

        ci_lo, ci_hi = r.accuracy_ci95
        table.add_row(
            r.benchmark_name,
            str(r.samples),
            f"{r.accuracy:.4f}",
            f"[{ci_lo:.3f},{ci_hi:.3f}]",
            _fmt_lat(r.p50_latency_ms),
            _fmt_lat(r.p95_latency_ms),
            f"{r.usage_total.prompt_tokens:,}",
            f"{r.usage_total.completion_tokens:,}",
            f"{r.usage_total.reasoning_tokens:,}",
            cost_str,
        )
        total_prompt += r.usage_total.prompt_tokens
        total_compl += r.usage_total.completion_tokens
        total_reason += r.usage_total.reasoning_tokens
        # Macro denominators
        denom = sum(v for k, v in r.error_breakdown.items() if k in ("ok", "wrong_answer"))
        n_scored += denom
        n_correct += r.correct_count

    table.add_section()
    avg = (n_correct / n_scored) if n_scored else 0.0
    table.add_row(
        "[bold]totals[/bold]",
        f"{sum(r.samples for r in results)}",
        f"{avg:.4f}",
        "—",
        "—",
        "—",
        f"{total_prompt:,}",
        f"{total_compl:,}",
        f"{total_reason:,}",
        (f"{total_cost:.4f}" if has_cost else "—"),
    )

    console.print(table)
