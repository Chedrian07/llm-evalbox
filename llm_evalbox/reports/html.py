# SPDX-License-Identifier: Apache-2.0
"""Single-file HTML export. No external assets — copy/share/host anywhere."""

from __future__ import annotations

import html
import json
from typing import Any

_TEMPLATE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>evalbox — {title}</title>
<style>
  body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
       max-width:64em;margin:2em auto;padding:0 1em;color:#222}}
  h1{{font-size:1.5em;margin-bottom:.2em}}
  .meta{{color:#666;font-size:.9em;margin-bottom:1.4em}}
  table{{width:100%;border-collapse:collapse;font-size:.9em;margin:1em 0}}
  th,td{{padding:.4em .6em;text-align:left;border-bottom:1px solid #ddd}}
  th{{background:#f7f7f7;text-transform:uppercase;font-size:.75em;letter-spacing:.05em;color:#555}}
  td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums}}
  pre{{background:#f7f7f7;padding:1em;border-radius:6px;overflow:auto;font-size:.85em}}
  details summary{{cursor:pointer;color:#555;margin:1em 0 .3em;font-size:.9em}}
  .tag{{display:inline-block;padding:0 .4em;background:#eef;border-radius:3px;font-size:.75em;color:#225}}
  .tag.warn{{background:#fee;color:#811}}
</style>
</head><body>
{body}
</body></html>
"""


def _fmt(n: float | None, digits: int = 4) -> str:
    return "—" if n is None else f"{n:.{digits}f}"


def _fmt_int(n: int | None) -> str:
    return "—" if n is None else f"{n:,}"


def _fmt_cost(c: float | None) -> str:
    return "—" if c is None else f"${c:.4f}"


def _fmt_lat(ms: float | None) -> str:
    if ms is None or ms == 0:
        return "—"
    return f"{ms/1000:.2f}s" if ms >= 1000 else f"{ms:.0f}ms"


def render_run_html(payload: dict[str, Any]) -> str:
    p = payload.get("provider", {})
    th = payload.get("thinking", {})
    totals = payload.get("totals", {})

    rows = []
    for b in payload.get("benchmarks", []) or []:
        ci = b.get("accuracy_ci95") or [0, 0]
        tk = b.get("tokens", {}) or {}
        lat = b.get("latency_ms", {}) or {}
        tag_strict = ' <span class="tag">strict</span>' if b.get("denominator_policy") == "strict" else ""
        tag_think = ' <span class="tag">think</span>' if b.get("thinking_used") else ""
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(b.get('name', '')))}{tag_think}{tag_strict}</td>"
            f"<td class='num'>{b.get('samples', 0)}</td>"
            f"<td class='num'>{_fmt(b.get('accuracy', 0), 4)}</td>"
            f"<td class='num' style='color:#666'>[{ci[0]:.2f}, {ci[1]:.2f}]</td>"
            f"<td class='num'>{_fmt_lat(lat.get('p50'))}</td>"
            f"<td class='num'>{_fmt_lat(lat.get('p95'))}</td>"
            f"<td class='num'>{_fmt_int(tk.get('prompt'))}</td>"
            f"<td class='num'>{_fmt_int(tk.get('completion'))}</td>"
            f"<td class='num'>{_fmt_int(tk.get('reasoning'))}</td>"
            f"<td class='num'>{_fmt_cost(b.get('cost_usd_estimated'))}</td>"
            "</tr>"
        )

    body = f"""
<h1>evalbox · {html.escape(p.get('model', '?'))}</h1>
<div class="meta">
  <code>{html.escape(p.get('base_url', '?'))}</code>
  · adapter <code>{html.escape(p.get('adapter', '?'))}</code>
  · thinking <code>{html.escape(th.get('mode', '?'))}</code> (used: {bool(th.get('used'))})
  · started <code>{html.escape(str(payload.get('started_at', '?')))}</code>
  → finished <code>{html.escape(str(payload.get('finished_at', '?')))}</code>
</div>
<p><strong>macro accuracy</strong> {_fmt(totals.get('accuracy_macro', 0), 4)}
  · <strong>total cost</strong> {_fmt_cost(totals.get('cost_usd_estimated'))}</p>
<table>
  <thead><tr>
    <th>benchmark</th><th class="num">samples</th><th class="num">accuracy</th>
    <th class="num">CI95</th><th class="num">p50</th><th class="num">p95</th>
    <th class="num">prompt</th><th class="num">compl.</th><th class="num">reasoning</th>
    <th class="num">cost USD</th>
  </tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table>
<details><summary>raw result.json</summary>
<pre>{html.escape(json.dumps(payload, indent=2, ensure_ascii=False))}</pre>
</details>
"""
    return _TEMPLATE.format(title=html.escape(p.get("model", "evalbox")), body=body)
