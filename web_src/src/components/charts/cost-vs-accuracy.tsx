import {
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { HistoryEntry } from "@/lib/history";

/**
 * Cost (x) vs accuracy (y) scatter — one point per (run, bench).
 * Color encodes the model so two runs with the same model use the same color.
 */

const COLORS = [
  "hsl(212 90% 60%)",
  "hsl(150 70% 55%)",
  "hsl(22 90% 60%)",
  "hsl(280 70% 65%)",
  "hsl(340 80% 60%)",
  "hsl(180 70% 55%)",
];

interface Props {
  runs: HistoryEntry[];
}

export function CostVsAccuracyChart({ runs }: Props) {
  if (runs.length === 0) {
    return <p className="text-sm text-muted-foreground">No runs in history yet.</p>;
  }

  const byModel = new Map<string, any[]>();
  for (const r of runs) {
    const model = r.model || "?";
    for (const b of r.result?.benchmarks ?? []) {
      const cost = b.cost_usd_estimated;
      const acc = b.accuracy;
      if (cost == null || acc == null) continue;
      if (!byModel.has(model)) byModel.set(model, []);
      byModel.get(model)!.push({
        x: cost,
        y: acc,
        bench: b.name,
        run_id: r.run_id,
      });
    }
  }

  const series = Array.from(byModel.entries()).map(([model, points], i) => ({
    name: model,
    data: points,
    color: COLORS[i % COLORS.length],
  }));

  return (
    <ResponsiveContainer width="100%" height={360}>
      <ScatterChart>
        <CartesianGrid strokeOpacity={0.2} />
        <XAxis
          type="number"
          dataKey="x"
          name="cost"
          unit=" USD"
          tick={{ fontSize: 11 }}
        />
        <YAxis
          type="number"
          dataKey="y"
          name="accuracy"
          domain={[0, 1]}
          tick={{ fontSize: 11 }}
        />
        <Tooltip
          cursor={{ strokeDasharray: "3 3" }}
          contentStyle={{
            background: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
          }}
          formatter={(v: any, n: string) => {
            if (n === "x") return [`$${v.toFixed(4)}`, "cost"];
            if (n === "y") return [v.toFixed(3), "accuracy"];
            return [v, n];
          }}
          labelFormatter={(_, payload) => {
            const p = (payload && payload[0]?.payload) as any;
            return p ? `${p.bench}` : "";
          }}
        />
        <Legend />
        {series.map((s) => (
          <Scatter key={s.name} name={s.name} data={s.data} fill={s.color} />
        ))}
      </ScatterChart>
    </ResponsiveContainer>
  );
}
