import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart as RechartsRadar,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from "recharts";

import type { HistoryEntry } from "@/lib/history";

/**
 * Per-category accuracy radar across multiple runs (models).
 * Categories are taken from each bench's `category` (knowledge / reasoning /
 * math / coding / truthful / multilingual / safety).
 *
 * We use the static category map maintained on the backend (web/routes/benchmarks.py).
 */

const BENCH_CATEGORY: Record<string, string> = {
  mmlu: "knowledge",
  mmlu_pro: "knowledge",
  arc_challenge: "knowledge",
  hellaswag: "reasoning",
  winogrande: "reasoning",
  gsm8k: "math",
  mathqa: "math",
  humaneval: "coding",
  mbpp: "coding",
  livecodebench: "coding",
  truthfulqa: "truthful",
  kmmlu: "multilingual",
  cmmlu: "multilingual",
  jmmlu: "multilingual",
  bbq: "safety",
  safetybench: "safety",
};

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

type RadarRow = { category: string } & Record<string, string | number>;

export function RadarChartComparison({ runs }: Props) {
  if (runs.length === 0) {
    return <p className="text-sm text-muted-foreground">No runs in history yet.</p>;
  }

  // Build {category: {model: avgAcc}}.
  const cats: Record<string, Record<string, { sum: number; n: number }>> = {};
  for (const r of runs) {
    const model = r.model || "?";
    for (const b of r.result?.benchmarks ?? []) {
      const cat = BENCH_CATEGORY[b.name] ?? "other";
      if (!cats[cat]) cats[cat] = {};
      if (!cats[cat][model]) cats[cat][model] = { sum: 0, n: 0 };
      cats[cat][model].sum += b.accuracy ?? 0;
      cats[cat][model].n += 1;
    }
  }

  const data: RadarRow[] = Object.entries(cats).map(([cat, byModel]) => {
    const row: RadarRow = { category: cat };
    for (const [model, agg] of Object.entries(byModel)) {
      row[model] = agg.n > 0 ? agg.sum / agg.n : 0;
    }
    return row;
  });

  const models = Array.from(
    new Set(runs.map((r) => r.model || "?"))
  );

  return (
    <ResponsiveContainer width="100%" height={360}>
      <RechartsRadar data={data}>
        <PolarGrid strokeOpacity={0.25} />
        <PolarAngleAxis dataKey="category" tick={{ fontSize: 12 }} />
        <PolarRadiusAxis domain={[0, 1]} tick={{ fontSize: 10 }} />
        {models.map((m, i) => (
          <Radar
            key={m}
            name={m}
            dataKey={m}
            stroke={COLORS[i % COLORS.length]}
            fill={COLORS[i % COLORS.length]}
            fillOpacity={0.18}
          />
        ))}
        <Tooltip
          contentStyle={{
            background: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
          }}
        />
        <Legend />
      </RechartsRadar>
    </ResponsiveContainer>
  );
}
