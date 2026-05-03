import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import type { HistoryEntry } from "@/lib/history";

/**
 * Side-by-side per-bench comparison between two history entries.
 * The schema only carries aggregate per-bench stats (no per-question data
 * unless `result.questions.jsonl` was kept), so we render the per-bench
 * accuracy + cost + p95 deltas for any benches both runs evaluated.
 */

interface Props {
  runs: HistoryEntry[];
}

export function AnswerDiff({ runs }: Props) {
  const [aId, setA] = useState<string>(runs[0]?.run_id ?? "");
  const [bId, setB] = useState<string>(runs[1]?.run_id ?? runs[0]?.run_id ?? "");

  const a = runs.find((r) => r.run_id === aId);
  const b = runs.find((r) => r.run_id === bId);

  const rows = useMemo(() => {
    if (!a || !b) return [];
    const ba = new Map<string, any>(
      (a.result?.benchmarks ?? []).map((x: any) => [x.name, x])
    );
    const bb = new Map<string, any>(
      (b.result?.benchmarks ?? []).map((x: any) => [x.name, x])
    );
    const names = Array.from(new Set([...ba.keys(), ...bb.keys()])).sort();
    return names.map((n) => {
      const x = ba.get(n);
      const y = bb.get(n);
      const dAcc = x && y ? (y.accuracy ?? 0) - (x.accuracy ?? 0) : null;
      const dCost = x && y ? (y.cost_usd_estimated ?? 0) - (x.cost_usd_estimated ?? 0) : null;
      return { n, x, y, dAcc, dCost };
    });
  }, [a, b]);

  if (runs.length < 2) {
    return <p className="text-sm text-muted-foreground">Need at least 2 runs in history.</p>;
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted-foreground">A:</span>
        <select
          className="rounded-md border border-input bg-transparent px-2 py-1"
          value={aId}
          onChange={(e) => setA(e.target.value)}
        >
          {runs.map((r) => (
            <option key={r.run_id} value={r.run_id}>
              {r.model} · {r.run_id.slice(-8)}
            </option>
          ))}
        </select>
        <span className="text-muted-foreground">B:</span>
        <select
          className="rounded-md border border-input bg-transparent px-2 py-1"
          value={bId}
          onChange={(e) => setB(e.target.value)}
        >
          {runs.map((r) => (
            <option key={r.run_id} value={r.run_id}>
              {r.model} · {r.run_id.slice(-8)}
            </option>
          ))}
        </select>
      </div>

      {a && b && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-2 py-2 text-left">benchmark</th>
                <th className="px-2 py-2 text-right">A · {a.model}</th>
                <th className="px-2 py-2 text-right">B · {b.model}</th>
                <th className="px-2 py-2 text-right">Δacc</th>
                <th className="px-2 py-2 text-right">Δcost</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.n} className="border-b last:border-b-0">
                  <td className="px-2 py-2">{r.n}</td>
                  <td className="px-2 py-2 text-right tabular-nums">
                    {r.x ? r.x.accuracy?.toFixed(3) : "—"}
                  </td>
                  <td className="px-2 py-2 text-right tabular-nums">
                    {r.y ? r.y.accuracy?.toFixed(3) : "—"}
                  </td>
                  <td className="px-2 py-2 text-right tabular-nums">
                    {r.dAcc == null ? "—" : (
                      <Badge variant={r.dAcc > 0 ? "success" : r.dAcc < 0 ? "destructive" : "outline"}>
                        {r.dAcc > 0 ? "+" : ""}
                        {r.dAcc.toFixed(3)}
                      </Badge>
                    )}
                  </td>
                  <td className="px-2 py-2 text-right tabular-nums">
                    {r.dCost == null ? "—" : `${r.dCost > 0 ? "+" : ""}$${r.dCost.toFixed(4)}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
