import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConnectionCard } from "@/components/connection-card";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import { subscribeRun } from "@/lib/sse";
import { useApp } from "@/lib/store";
import { fmtAcc } from "@/lib/format";

interface AccumPoint {
  done: number;
  acc: number;
}

export function RunningPage() {
  const { t } = useTranslation();
  const s = useApp();
  const [series, setSeries] = useState<AccumPoint[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!s.runId) return;
    const unsub = subscribeRun(s.runId, {
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
        const detail = await api.getRun(s.runId!);
        s.setFinalResult(detail.result ?? null);
        s.setStage("results");
      },
      onError: (data) => {
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

  return (
    <div className="space-y-4">
      <ConnectionCard compact />

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
        <CardContent className="space-y-2">
          <Progress value={overallPct} />
          <p className="text-xs text-muted-foreground tabular-nums">
            {totalCurrent} / {totalTotal} ({overallPct.toFixed(0)}%)
          </p>
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
  );
}
