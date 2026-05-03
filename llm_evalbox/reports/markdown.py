# SPDX-License-Identifier: Apache-2.0
"""Render result.json (single run or compare) as portable Markdown."""

from __future__ import annotations

from typing import Any


def _fmt_lat(ms: float | None) -> str:
    if ms is None or ms == 0:
        return "—"
    return f"{ms/1000:.2f}s" if ms >= 1000 else f"{ms:.0f}ms"


def _fmt_cost(c: float | None) -> str:
    return "—" if c is None else f"${c:.4f}"


def render_run_md(payload: dict[str, Any]) -> str:
    """Render a single result.json payload as Markdown."""
    lines: list[str] = []
    p = payload.get("provider", {})
    lines.append(f"# evalbox run — {payload.get('run_id', '?')}")
    lines.append("")
    lines.append(f"- **model** `{p.get('model', '?')}`")
    lines.append(f"- **base_url** `{p.get('base_url', '?')}`  (adapter `{p.get('adapter', '?')}`)")
    lines.append(f"- **started_at** {payload.get('started_at', '?')}  →  **finished_at** {payload.get('finished_at', '?')}")
    th = payload.get("thinking", {})
    lines.append(f"- **thinking** mode=`{th.get('mode', '?')}`, used={th.get('used')}")
    lines.append(f"- **strict_failures** {payload.get('strict_failures', False)}")
    totals = payload.get("totals", {})
    lines.append(f"- **macro accuracy** {totals.get('accuracy_macro', 0):.4f}")
    lines.append(f"- **total cost** { _fmt_cost(totals.get('cost_usd_estimated'))}")
    lines.append("")

    lines.append("| benchmark | samples | accuracy | CI95 | p50 | p95 | prompt | compl. | reasoning | cost | denom |")
    lines.append("|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---|")
    for b in payload.get("benchmarks", []) or []:
        ci = b.get("accuracy_ci95") or [0, 0]
        tk = b.get("tokens", {}) or {}
        lat = b.get("latency_ms", {}) or {}
        lines.append(
            f"| {b.get('name')} "
            f"| {b.get('samples', 0)} "
            f"| {b.get('accuracy', 0):.4f} "
            f"| [{ci[0]:.2f}, {ci[1]:.2f}] "
            f"| {_fmt_lat(lat.get('p50'))} "
            f"| {_fmt_lat(lat.get('p95'))} "
            f"| {tk.get('prompt', 0):,} "
            f"| {tk.get('completion', 0):,} "
            f"| {tk.get('reasoning', 0):,} "
            f"| {_fmt_cost(b.get('cost_usd_estimated'))} "
            f"| {b.get('denominator_policy', '?')} |"
        )
    return "\n".join(lines) + "\n"


def render_compare_md(payloads: list[dict[str, Any]]) -> str:
    """Render multiple result.json payloads side-by-side."""
    lines: list[str] = []
    lines.append("# evalbox compare")
    lines.append("")
    if not payloads:
        return "\n".join(lines) + "\n"
    header_cells = ["| benchmark"]
    for p in payloads:
        header_cells.append(f"| {p.get('provider', {}).get('model', '?')}")
    header_cells.append("|")
    lines.append(" ".join(header_cells))
    lines.append("|" + "|".join(["---"] * (len(payloads) + 1)) + "|")

    bench_names: list[str] = []
    for p in payloads:
        for b in p.get("benchmarks", []) or []:
            if b["name"] not in bench_names:
                bench_names.append(b["name"])

    for name in bench_names:
        row = [f"| {name}"]
        for p in payloads:
            cell = "—"
            for b in p.get("benchmarks", []) or []:
                if b["name"] == name:
                    cell = f"{b.get('accuracy', 0):.4f} ({_fmt_cost(b.get('cost_usd_estimated'))})"
                    break
            row.append(f"| {cell}")
        row.append("|")
        lines.append(" ".join(row))
    return "\n".join(lines) + "\n"
