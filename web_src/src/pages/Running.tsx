import { type Dispatch, type SetStateAction, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConnectionCard } from "@/components/connection-card";
import { Progress } from "@/components/ui/progress";
import { RunMessages } from "@/components/run-messages";
import { api, type RunMessage } from "@/lib/api";
import { subscribeRun } from "@/lib/sse";
import { useApp } from "@/lib/store";
import { fmtAcc, fmtCost } from "@/lib/format";

interface AccumPoint {
  done: number;
  acc: number;
}

export function RunningPage() {
  const { t } = useTranslation();
  const s = useApp();
  const [series, setSeries] = useState<AccumPoint[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<RunMessage[]>([]);
  const [now, setNow] = useState(Date.now());
  const [startedAt] = useState(Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    if (!s.runId) return;
    const unsub = subscribeRun(s.runId, {
      onAny: (_type, data) => {
        pushMessage(setMessages, data);
      },
      onProgress: (data) => {
        s.updateBenchProgress(data.bench, {
          current: data.current,
          total: data.total,
          running_accuracy: data.running_accuracy,
          thinking_used: data.thinking_used,
        });
        setSeries((prev) => {
          const all = Object.values(useApp.getState().benchProgress);
          const totalDone = all.reduce((acc, b) => acc + b.current, 0);
          const acc = data.running_accuracy ?? 0;
          if (totalDone > 0)
            return [...prev, { done: totalDone, acc }].slice(-200);
          return prev;
        });
      },
      onResult: (data) => {
        s.updateBenchProgress(data.bench, {
          done: true,
          result: data.data,
        });
      },
      onDone: async () => {
        try {
          const detail = await api.getRun(s.runId!);
          s.setFinalResult(detail.result
            ? { ...detail.result, messages: detail.result.messages ?? detail.messages ?? [] }
            : null);
          s.setStage("results");
        } catch (e) {
          setError(e instanceof Error ? e.message : String(e));
        }
      },
      onError: (data) => {
        if (!data?.type) {
          pushMessage(setMessages, {
            type: "error",
            message: data.message ?? "stream error",
          });
        }
        setError(data.message ?? "stream error");
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
  const etaMs = rate > 0 && totalTotal > totalCurrent
    ? ((totalTotal - totalCurrent) / rate) * 1000
    : null;

  return (
    <div className="space-y-4">
      <ConnectionCard compact />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <RunStat label={t("run.progress")} value={`${overallPct.toFixed(0)}%`} detail={`${totalCurrent}/${totalTotal || "?"}`} />
        <RunStat label={t("run.cost_so_far")} value={fmtCost(costSoFar)} detail={s.maxCostUsd == null ? t("run.no_cap") : `${fmtCost(s.maxCostUsd)} cap`} />
        <RunStat label={t("run.elapsed")} value={fmtDuration(elapsedMs)} detail={etaMs == null ? t("run.eta_unknown") : `${t("run.eta")} ${fmtDuration(etaMs)}`} />
        <RunStat label={t("run.active_benches")} value={String(benches.filter((b) => !b.done).length || benches.length)} detail={benches.some((b) => b.thinking_used) ? t("run.thinking_on") : s.thinking} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="min-w-0 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>{t("stage.running")}</span>
                <div className="flex items-center gap-2">
                  {benches.some((b) => b.thinking_used) && (
                    <Badge variant="success">{t("run.thinking_on")}</Badge>
                  )}
                  <Button size="sm" variant="destructive" onClick={cancel}>
                    {t("run.cancel")}
                  </Button>
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Progress value={overallPct} />
              <p className="text-xs text-muted-foreground tabular-nums">
                {totalCurrent} / {totalTotal} ({overallPct.toFixed(0)}%)
              </p>
              {/* Cumulative cost vs cap. Each `result` SSE event carries the
                  per-bench cost; we sum what we've seen so far. */}
              {(() => {
                const cap = s.maxCostUsd;
                const pct = cap && cap > 0 ? Math.min(100, (costSoFar / cap) * 100) : null;
                const over = cap != null && cap > 0 && costSoFar >= cap;
                return (
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs tabular-nums">
                      <span className="text-muted-foreground">
                        cost so far: <span className={over ? "text-destructive font-semibold" : ""}>
                          ${costSoFar.toFixed(4)}
                        </span>
                        {cap == null ? "" : ` / $${cap.toFixed(2)}`}
                      </span>
                      {pct != null && (
                        <span className={over ? "text-destructive" : "text-muted-foreground"}>
                          {pct.toFixed(0)}%
                        </span>
                      )}
                    </div>
                    {pct != null && (
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
                        <div
                          className={over ? "h-full bg-destructive" : "h-full bg-emerald-500"}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    )}
                  </div>
                );
              })()}
              {error && <p className="text-sm text-destructive">{error}</p>}
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
            <Card>
              <CardHeader>
                <CardTitle>{t("benches.title")}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {benches.map((b) => (
                  <div key={b.bench} className="space-y-1">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium">{b.bench}</span>
                      <span className="text-muted-foreground tabular-nums">
                        {b.current}/{b.total} · acc={fmtAcc(b.running_accuracy)}
                        {b.done && " ✓"}
                      </span>
                    </div>
                    <Progress value={b.total > 0 ? (b.current / b.total) * 100 : 0} />
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t("run.running_accuracy")}</CardTitle>
              </CardHeader>
              <CardContent className="h-64">
                {series.length > 1 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={series}>
                      <CartesianGrid strokeOpacity={0.1} />
                      <XAxis dataKey="done" stroke="currentColor" fontSize={12} />
                      <YAxis domain={[0, 1]} stroke="currentColor" fontSize={12} />
                      <Tooltip
                        contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }}
                      />
                      <Line type="monotone" dataKey="acc" stroke="hsl(var(--primary))" dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-sm text-muted-foreground">…</p>
                )}
              </CardContent>
            </Card>
          </div>
        </div>

        <aside className="xl:sticky xl:top-20 xl:self-start">
          <Card>
            <CardHeader>
              <CardTitle>{t("run.messages")}</CardTitle>
            </CardHeader>
            <CardContent>
              <RunMessages messages={messages} empty="—" />
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}

function pushMessage(
  setMessages: Dispatch<SetStateAction<RunMessage[]>>,
  event: any,
) {
  const message = runMessageFromEvent(event);
  if (!message) return;
  setMessages((prev) => [...prev, message].slice(-80));
}

function runMessageFromEvent(event: any): RunMessage | null {
  if (!event || event.type === "ping") return null;
  const type = String(event.type ?? "message");
  const created_at = event.created_at ?? new Date().toISOString();
  const content = typeof event.message === "string"
    ? event.message
    : fallbackMessageContent(event);
  const metadata = Object.fromEntries(
    Object.entries(event).filter(([key]) => key !== "message" && key !== "created_at"),
  );
  return {
    role: type === "result" || type === "done" ? "assistant" : "system",
    content,
    created_at,
    metadata,
  };
}

function fallbackMessageContent(event: any): string {
  if (event.type === "progress") {
    if (event.phase === "loading") return `${event.bench}: loading dataset`;
    return `${event.bench}: ${event.current ?? 0}/${event.total ?? "?"}`;
  }
  if (event.type === "result") return `${event.bench}: completed`;
  if (event.type === "done") return "run completed";
  if (event.type === "error") return event.message ?? "run error";
  return String(event.type ?? "message");
}

function RunStat({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs uppercase text-muted-foreground">{label}</div>
        <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
        <div className="mt-1 truncate text-xs text-muted-foreground">{detail}</div>
      </CardContent>
    </Card>
  );
}

function fmtDuration(ms: number): string {
  const seconds = Math.max(0, Math.round(ms / 1000));
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}
