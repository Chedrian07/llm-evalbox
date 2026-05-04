import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Activity,
  Brain,
  CheckCircle2,
  Clock,
  Coins,
  Layers,
  TrendingUp,
} from "lucide-react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConnectionCard } from "@/components/connection-card";
import { Progress } from "@/components/ui/progress";
import { LiveLogPanel, type LogEntry } from "@/components/live-log-panel";
import { api } from "@/lib/api";
import { subscribeRun } from "@/lib/sse";
import { useApp } from "@/lib/store";
import { fmtAccLive, fmtCap, fmtCost, fmtElapsed } from "@/lib/format";
import { cn } from "@/lib/cn";

interface BenchPoint {
  x: number;
  acc: number;
}

// Distinct colors so each bench's line stays readable. The first color is
// the brand emerald so a single-bench run still feels native.
const BENCH_COLORS = [
  "hsl(152, 64%, 50%)", // emerald (primary)
  "hsl(206, 90%, 60%)", // blue
  "hsl(38, 92%, 60%)",  // amber
  "hsl(280, 70%, 65%)", // violet
  "hsl(330, 78%, 65%)", // pink
  "hsl(180, 70%, 55%)", // cyan
  "hsl(15, 85%, 60%)",  // orange
  "hsl(60, 80%, 55%)",  // yellow
];

export function RunningPage() {
  const { t } = useTranslation();
  const s = useApp();
  const [seriesByBench, setSeriesByBench] = useState<Record<string, BenchPoint[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [logEntries, setLogEntries] = useState<LogEntry[]>([]);
  const [now, setNow] = useState(Date.now());
  const [startedAt] = useState(Date.now());
  const logIdRef = useRef(0);

  function appendLog(partial: Omit<LogEntry, "id" | "ts">, ts?: number) {
    setLogEntries((prev) => [
      ...prev,
      { id: ++logIdRef.current, ts: ts ?? Date.now(), ...partial },
    ].slice(-3000));
  }

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    if (!s.runId) return;
    const unsub = subscribeRun(s.runId, {
      onAny: (type, data) => {
        // Generic system / status / error / done lines all go through here.
        // The per-type handlers below add richer entries for "item" and
        // similarly skip system entries we already covered.
        if (type === "ping" || type === "item" || type === "progress") return;
        if (type === "result") return; // handled below with bench name
        if (type === "done") {
          appendLog({
            kind: "done",
            text: data?.message ?? "run completed",
          });
          return;
        }
        if (type === "error") {
          appendLog({
            kind: "error",
            text: data?.message ?? "stream error",
          });
          return;
        }
        appendLog({
          kind: "system",
          text:
            typeof data?.message === "string"
              ? data.message
              : `${type}: ${JSON.stringify(data ?? {}).slice(0, 200)}`,
        });
      },
      onProgress: (data) => {
        s.updateBenchProgress(data.bench, {
          current: data.current,
          total: data.total,
          running_accuracy: data.running_accuracy,
          thinking_used: data.thinking_used,
        });
        // Per-bench series so each benchmark gets its own line. Plotting
        // a single global line caused the chart to drop to zero whenever
        // a new bench started.
        if (data.bench && typeof data.current === "number" && data.current > 0) {
          const point = { x: data.current, acc: data.running_accuracy ?? 0 };
          setSeriesByBench((prev) => {
            const cur = prev[data.bench] ?? [];
            // De-dupe consecutive same-x updates (multiple progress events
            // can fire for the same `current` if the auto-thinking rerun
            // re-emits a batch).
            const last = cur[cur.length - 1];
            const next = last && last.x === point.x ? [...cur.slice(0, -1), point] : [...cur, point];
            return { ...prev, [data.bench]: next.slice(-200) };
          });
        }
        // Progress lines flood the log; we still surface them but the panel
        // can hide them via its toolbar toggle.
        if (data?.phase === "loading") {
          appendLog({
            kind: "system",
            bench: data.bench,
            text: "loading dataset",
          });
        }
      },
      onItem: (data) => {
        appendLog({
          kind: "item",
          bench: data.bench,
          index: data.index,
          total: data.total,
          correct: !!data.correct,
          errorKind: data.error_kind,
          expected: data.expected,
          predicted: data.predicted,
          promptPreview: data.prompt_preview,
          textPreview: data.text_preview,
          reasoningPreview: data.reasoning_preview,
          latencyMs: data.latency_ms,
          cacheHit: !!data.cache_hit,
          tokens: data.tokens,
          text: "",
        });
      },
      onResult: (data) => {
        s.updateBenchProgress(data.bench, { done: true, result: data.data });
        const acc = data?.data?.accuracy;
        const cost = data?.data?.cost_usd;
        const parts = [`completed`];
        if (typeof acc === "number") parts.push(`acc=${acc.toFixed(3)}`);
        if (typeof cost === "number") parts.push(`cost=$${cost.toFixed(4)}`);
        appendLog({
          kind: "result",
          bench: data.bench,
          text: parts.join(" · "),
        });
      },
      onDone: async () => {
        try {
          const detail = await api.getRun(s.runId!);
          s.setFinalResult(
            detail.result
              ? { ...detail.result, messages: detail.result.messages ?? detail.messages ?? [] }
              : null,
          );
          s.setStage("results");
        } catch (e) {
          setError(e instanceof Error ? e.message : String(e));
        }
      },
      onError: (data) => {
        appendLog({ kind: "error", text: data?.message ?? "stream error" });
        setError(data?.message ?? "stream error");
      },
    });
    return unsub;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s.runId]);

  async function cancel() {
    if (s.runId) await api.cancelRun(s.runId).catch(() => {});
    s.setStage("setup");
  }

  const benches = Object.values(s.benchProgress).sort((a, b) => a.bench.localeCompare(b.bench));
  const totalCurrent = benches.reduce((acc, b) => acc + b.current, 0);
  const totalTotal = benches.reduce((acc, b) => acc + b.total, 0);
  const overallPct = totalTotal > 0 ? (totalCurrent / totalTotal) * 100 : 0;
  const costSoFar = benches.reduce((acc, b) => acc + (b.result?.cost_usd ?? 0), 0);
  const elapsedMs = now - startedAt;
  const rate = elapsedMs > 0 ? totalCurrent / (elapsedMs / 1000) : 0;
  const etaMs =
    rate > 0 && totalTotal > totalCurrent ? ((totalTotal - totalCurrent) / rate) * 1000 : null;

  // Build combined chart data: one row per x value, one column per bench.
  // recharts plots multiple <Line dataKey={bench} /> against this shape; gaps
  // are rendered as breaks in the line, so each bench appears independently.
  const benchNames = useMemo(() => Object.keys(seriesByBench).sort(), [seriesByBench]);
  const chartData = useMemo(() => {
    const maxX = benchNames.reduce((acc, n) => {
      const last = seriesByBench[n][seriesByBench[n].length - 1];
      return last ? Math.max(acc, last.x) : acc;
    }, 0);
    if (maxX === 0) return [];
    const rows: Array<Record<string, number>> = [];
    for (let x = 1; x <= maxX; x++) {
      const row: Record<string, number> = { x };
      for (const n of benchNames) {
        const point = seriesByBench[n].find((p) => p.x === x);
        if (point) row[n] = point.acc;
      }
      rows.push(row);
    }
    return rows;
  }, [benchNames, seriesByBench]);
  const totalChartPoints = benchNames.reduce((acc, n) => acc + (seriesByBench[n]?.length ?? 0), 0);

  const cap = fmtCap(s.maxCostUsd);
  const capProgressPct =
    !cap.effectivelyNoCap && s.maxCostUsd && s.maxCostUsd > 0
      ? Math.min(100, (costSoFar / s.maxCostUsd) * 100)
      : null;
  const capExceeded =
    !cap.effectivelyNoCap && s.maxCostUsd != null && costSoFar >= s.maxCostUsd;
  const activeCount = benches.filter((b) => !b.done).length;
  const completedCount = benches.filter((b) => b.done).length;
  const anyThinking = benches.some((b) => b.thinking_used);

  return (
    <div className="space-y-4">
      <ConnectionCard compact />

      {/* Hero progress card — overall progress + key metrics + cancel */}
      <section className="overflow-hidden rounded-lg border border-primary/20 bg-gradient-to-b from-primary/[0.06] to-transparent">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border/40 px-4 py-3">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-primary" />
            <h2 className="text-base font-semibold leading-none">{t("stage.running")}</h2>
            {anyThinking && (
              <Badge
                variant="outline"
                className="animate-pulse border-primary/40 bg-primary/10 text-primary"
              >
                <Brain className="h-3 w-3" />
                {t("run.thinking_on")}
              </Badge>
            )}
          </div>
          <Button size="sm" variant="destructive" onClick={cancel} className="h-8">
            {t("run.cancel")}
          </Button>
        </header>

        <div className="grid gap-3 p-4 lg:grid-cols-[2fr_3fr]">
          {/* Big number + global progress */}
          <div>
            <div className="text-[0.7rem] uppercase tracking-wide text-muted-foreground">
              {t("run.progress")}
            </div>
            <div className="mt-1 flex items-baseline gap-2 font-mono text-3xl font-semibold tabular-nums">
              <span>{totalCurrent}</span>
              <span className="text-muted-foreground">/</span>
              <span className="text-muted-foreground">{totalTotal || "?"}</span>
              <span className="ml-1 text-base text-primary">({overallPct.toFixed(0)}%)</span>
            </div>
            <Progress value={overallPct} className="mt-3" />
            {error && <p className="mt-2 text-xs text-destructive">{error}</p>}
          </div>

          {/* Stat row */}
          <div className="grid grid-cols-3 divide-x divide-border/40 rounded-md border border-border/40 bg-background/40">
            <CompactStat
              icon={<Coins className="h-3 w-3" />}
              label={t("run.cost_so_far")}
              value={fmtCost(costSoFar)}
              detail={cap.label}
              detailTone={capExceeded ? "destructive" : "muted"}
            />
            <CompactStat
              icon={<Clock className="h-3 w-3" />}
              label={t("run.elapsed")}
              value={fmtElapsed(elapsedMs)}
              detail={
                etaMs == null
                  ? t("run.eta_unknown")
                  : `${t("run.eta")} ${fmtElapsed(etaMs)}`
              }
            />
            <CompactStat
              icon={<Layers className="h-3 w-3" />}
              label={t("run.active_benches")}
              value={
                activeCount > 0
                  ? `${activeCount}`
                  : completedCount > 0
                    ? `${completedCount} ✓`
                    : "—"
              }
              detail={
                completedCount > 0 && activeCount > 0
                  ? `${completedCount} done`
                  : anyThinking
                    ? t("run.thinking_on")
                    : s.thinking
              }
            />
          </div>
        </div>

        {/* Cap bar — only render if there's a real cap */}
        {capProgressPct != null && (
          <div className="border-t border-border/40 px-4 py-2">
            <div className="flex items-center justify-between text-[0.7rem] uppercase tracking-wide text-muted-foreground">
              <span>{t("run.cost_so_far")}</span>
              <span
                className={cn(
                  "font-mono normal-case tracking-normal",
                  capExceeded ? "text-destructive" : "text-foreground",
                )}
              >
                {fmtCost(costSoFar)} / ${(s.maxCostUsd ?? 0).toFixed(2)} ·{" "}
                {capProgressPct.toFixed(0)}%
              </span>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-secondary">
              <div
                className={cn("h-full transition-all", capExceeded ? "bg-destructive" : "bg-primary")}
                style={{ width: `${capProgressPct}%` }}
              />
            </div>
          </div>
        )}
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(20rem,24rem)]">
        <div className="min-w-0 space-y-4">
          {/* Per-bench progress cards */}
          <section className="rounded-lg border border-border/60 surface-1">
            <header className="flex items-center justify-between border-b border-border/60 px-4 py-3">
              <h3 className="text-sm font-semibold">{t("run.active_benches")}</h3>
              <span className="text-xs text-muted-foreground tabular-nums">
                {completedCount}/{benches.length} done
              </span>
            </header>
            <div className="grid gap-2 p-3 sm:grid-cols-2">
              {benches.map((b) => (
                <BenchProgressCard
                  key={b.bench}
                  name={b.bench}
                  current={b.current}
                  total={b.total}
                  acc={b.running_accuracy}
                  thinking={b.thinking_used}
                  done={b.done}
                  costUsd={b.result?.cost_usd ?? null}
                />
              ))}
            </div>
          </section>

          {/* Running accuracy chart — one line per benchmark. The shared
              x-axis is "samples within the bench" so two benches running in
              series both start at 1, plotted against their own line. */}
          {totalChartPoints > 1 && (
            <section className="rounded-lg border border-border/60 surface-1">
              <header className="flex items-center gap-2 border-b border-border/60 px-4 py-3">
                <TrendingUp className="h-3.5 w-3.5 text-muted-foreground" />
                <h3 className="text-sm font-semibold">{t("run.running_accuracy")}</h3>
                <span className="text-[0.65rem] text-muted-foreground">
                  {t("run.per_bench", {
                    defaultValue: "per benchmark · x = sample index",
                  })}
                </span>
              </header>
              <div className="h-64 p-3">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeOpacity={0.08} />
                    <XAxis dataKey="x" stroke="currentColor" fontSize={11} />
                    <YAxis domain={[0, 1]} stroke="currentColor" fontSize={11} />
                    <Tooltip
                      contentStyle={{
                        background: "hsl(var(--card))",
                        border: "1px solid hsl(var(--border))",
                        borderRadius: "0.375rem",
                      }}
                      formatter={(value: any) => (typeof value === "number" ? value.toFixed(3) : value)}
                    />
                    <Legend
                      wrapperStyle={{ fontSize: 11 }}
                      iconType="plainline"
                      iconSize={14}
                    />
                    {benchNames.map((name, i) => (
                      <Line
                        key={name}
                        type="monotone"
                        dataKey={name}
                        stroke={BENCH_COLORS[i % BENCH_COLORS.length]}
                        strokeWidth={2}
                        dot={false}
                        connectNulls
                        isAnimationActive={false}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>
          )}
        </div>

        <aside className="xl:sticky xl:top-20 xl:self-start xl:h-[calc(100vh-6rem)]">
          <LiveLogPanel entries={logEntries} onClear={() => setLogEntries([])} />
        </aside>
      </div>
    </div>
  );
}

function CompactStat({
  icon,
  label,
  value,
  detail,
  detailTone = "muted",
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  detail: string;
  detailTone?: "muted" | "destructive";
}) {
  return (
    <div className="flex flex-col items-start gap-0.5 px-3 py-2">
      <span className="inline-flex items-center gap-1 text-[0.6rem] uppercase tracking-wide text-muted-foreground">
        {icon}
        {label}
      </span>
      <span className="font-mono text-base font-semibold tabular-nums">{value}</span>
      <span
        className={cn(
          "truncate text-[0.65rem]",
          detailTone === "destructive" ? "text-destructive" : "text-muted-foreground",
        )}
      >
        {detail}
      </span>
    </div>
  );
}

function BenchProgressCard({
  name,
  current,
  total,
  acc,
  thinking,
  done,
  costUsd,
}: {
  name: string;
  current: number;
  total: number;
  acc: number;
  thinking: boolean;
  done: boolean;
  costUsd: number | null;
}) {
  const pct = total > 0 ? (current / total) * 100 : 0;
  return (
    <div
      className={cn(
        "rounded-md border p-3 transition",
        done
          ? "border-primary/40 bg-primary/[0.06]"
          : "border-border/50 surface-2",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1.5">
          <span className="truncate font-medium">{name}</span>
          {done && <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-primary" />}
          {thinking && !done && (
            <Brain
              className="h-3.5 w-3.5 shrink-0 animate-pulse text-primary"
              aria-label="thinking"
            />
          )}
        </div>
        <span className="font-mono text-xs text-muted-foreground tabular-nums">
          {current}/{total}
        </span>
      </div>
      <Progress value={pct} className="mt-2 h-1.5" />
      <div className="mt-2 flex items-center justify-between text-[0.7rem] text-muted-foreground">
        <span>
          acc <span className="font-mono text-foreground/80">{fmtAccLive(acc, current)}</span>
        </span>
        {costUsd != null && (
          <span>
            cost <span className="font-mono text-foreground/80">{fmtCost(costUsd)}</span>
          </span>
        )}
      </div>
    </div>
  );
}

