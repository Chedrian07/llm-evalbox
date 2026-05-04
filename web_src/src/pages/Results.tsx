import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Download, Share2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConnectionCard } from "@/components/connection-card";
import { AnswerDiff } from "@/components/charts/answer-diff";
import { CostVsAccuracyChart } from "@/components/charts/cost-vs-accuracy";
import { RadarChartComparison } from "@/components/charts/radar-chart";
import { LiveLogPanel, messagesToLogEntries } from "@/components/live-log-panel";
import { RunHistorySidebar } from "@/components/run-history-sidebar";
import { RunMetaEditor } from "@/components/run-meta-editor";
import { api, type BenchmarkResult, type RunResult } from "@/lib/api";
import { useApp } from "@/lib/store";
import { listMergedHistory, saveHistory, type HistoryEntry } from "@/lib/history";
import { fmtAcc, fmtCost, fmtMs, fmtNum } from "@/lib/format";

type Tab = "matrix" | "radar" | "scatter" | "diff" | "messages" | "raw";

export function ResultsPage() {
  const { t } = useTranslation();
  const s = useApp();
  const [tab, setTab] = useState<Tab>("matrix");
  const [refreshKey, setRefreshKey] = useState(0);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [shareUrl, setShareUrl] = useState<string | null>(null);

  // Persist this run into IndexedDB once the result is available.
  useEffect(() => {
    if (s.finalResult && s.runId) {
      const entry: HistoryEntry = {
        run_id: s.runId,
        saved_at: Date.now(),
        model: s.finalResult.provider?.model ?? s.model,
        base_url: s.finalResult.provider?.base_url ?? s.baseUrl,
        result: s.finalResult,
      };
      saveHistory(entry)
        .then(() => setRefreshKey((k) => k + 1))
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s.finalResult, s.runId]);

  // Initial history load (used by Radar / Scatter / Diff even before a save).
  useEffect(() => {
    listMergedHistory()
      .then(setHistory)
      .catch(() => {});
  }, [refreshKey]);

  const r = s.finalResult;

  function exportFile(kind: "json" | "md" | "html") {
    if (!r) return;
    let body = "";
    let mime = "application/octet-stream";
    let filename = `${r.run_id}`;
    if (kind === "json") {
      body = JSON.stringify(r, null, 2);
      mime = "application/json";
      filename += ".json";
    } else if (kind === "md") {
      body = renderRunMd(r);
      mime = "text/markdown";
      filename += ".md";
    } else {
      body = renderRunHtml(r);
      mime = "text/html";
      filename += ".html";
    }
    const blob = new Blob([body], { type: mime });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function share() {
    if (!s.runId) return;
    const j = await api.shareRun(s.runId);
    setShareUrl(j.url);
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
      <div className="min-w-0 space-y-4">
        <ConnectionCard compact />
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>{t("results.title")}</span>
              <div className="flex flex-wrap items-center gap-1">
                <TabBtn label={t("results.matrix")} on={tab === "matrix"} onClick={() => setTab("matrix")} />
                <TabBtn label={t("results.radar")} on={tab === "radar"} onClick={() => setTab("radar")} />
                <TabBtn label={t("results.scatter")} on={tab === "scatter"} onClick={() => setTab("scatter")} />
                <TabBtn label={t("results.diff")} on={tab === "diff"} onClick={() => setTab("diff")} />
                <TabBtn label={t("results.messages")} on={tab === "messages"} onClick={() => setTab("messages")} />
                <TabBtn label={t("results.raw")} on={tab === "raw"} onClick={() => setTab("raw")} />
                <Button size="sm" variant="outline" onClick={() => exportFile("md")}>
                  <Download className="h-3 w-3" /> .md
                </Button>
                <Button size="sm" variant="outline" onClick={() => exportFile("html")}>
                  <Download className="h-3 w-3" /> .html
                </Button>
                <Button size="sm" variant="outline" onClick={() => exportFile("json")}>
                  <Download className="h-3 w-3" /> .json
                </Button>
                <Button size="sm" variant="outline" onClick={share}>
                  <Share2 className="h-3 w-3" />
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    s.setStage("setup");
                    s.setRunId(null);
                    s.setFinalResult(null);
                  }}
                >
                  {t("results.new_run")}
                </Button>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {shareUrl && (
              <p className="mb-3 text-xs text-muted-foreground">
                share: <code className="font-mono">{shareUrl}</code>
              </p>
            )}
            {!r ? (
              <p className="text-sm text-muted-foreground">…</p>
            ) : (
              <div className="space-y-4">
                {s.runId && (
                  <RunMetaEditor
                    runId={s.runId}
                    initialTags={
                      history.find((h) => h.run_id === s.runId)?.tags ?? []
                    }
                    initialNotes={
                      history.find((h) => h.run_id === s.runId)?.notes ?? ""
                    }
                    initialStarred={
                      history.find((h) => h.run_id === s.runId)?.starred ?? false
                    }
                  />
                )}
                <SummaryCards r={r} />
                {tab === "matrix" ? (
                  <Matrix r={r} />
                ) : tab === "radar" ? (
                  <RadarChartComparison runs={history} />
                ) : tab === "scatter" ? (
                  <CostVsAccuracyChart runs={history} />
                ) : tab === "diff" ? (
                  <AnswerDiff runs={history} />
                ) : tab === "messages" ? (
                  <div className="h-[70vh] min-h-[24rem]">
                    <LiveLogPanel
                      entries={messagesToLogEntries(r.messages ?? [])}
                      defaultAutoScroll={false}
                    />
                  </div>
                ) : (
                  <div className="max-h-[70vh] min-h-[24rem] overflow-auto rounded-md border border-border/40 bg-[hsl(222,30%,4%)]">
                    <pre className="whitespace-pre p-3 font-mono text-xs leading-relaxed text-foreground/90">
                      {JSON.stringify(r, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <RunHistorySidebar
        refreshKey={refreshKey}
        onChange={setHistory}
        onSelect={(entry) => {
          s.setRunId(entry.run_id);
          s.setFinalResult(entry.result);
        }}
      />
    </div>
  );
}

function TabBtn({ label, on, onClick }: { label: string; on: boolean; onClick: () => void }) {
  return (
    <Button size="sm" variant={on ? "default" : "ghost"} onClick={onClick}>
      {label}
    </Button>
  );
}

function SummaryCards({ r }: { r: RunResult }) {
  const { t } = useTranslation();
  const totals = r.totals ?? {};
  const tokens = totals.tokens ?? {};
  const benches = r.benchmarks ?? [];
  const sampleCount = benches.reduce((acc, b) => acc + (b.samples ?? 0), 0);
  const cacheHits = benches.reduce((acc, b) => acc + (b.cache_hits ?? 0), 0);
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <SummaryMetric label={t("results.accuracy")} value={fmtAcc(totals.accuracy_macro)} detail={t("results.macro")} />
      <SummaryMetric label={t("results.cost")} value={fmtCost(totals.cost_usd_estimated)} detail={r.provider?.model ?? "?"} />
      <SummaryMetric label={t("results.samples")} value={fmtNum(sampleCount)} detail={`${benches.length} ${t("plan.benchmarks")}`} />
      <SummaryMetric label={t("results.tokens")} value={fmtNum((tokens.prompt ?? 0) + (tokens.completion ?? 0) + (tokens.reasoning ?? 0))} detail={`cached ${fmtNum(tokens.cached_prompt)}`} />
      <SummaryMetric label={t("results.cache_hits")} value={fmtNum(cacheHits)} detail={r.sampling?.prompt_cache_aware ? t("options.prompt_cache_short") : t("results.response_cache")} />
    </div>
  );
}

function SummaryMetric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-md border border-input p-3">
      <div className="text-[0.7rem] uppercase text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{value}</div>
      <div className="mt-1 truncate text-xs text-muted-foreground">{detail}</div>
    </div>
  );
}

function Matrix({ r }: { r: RunResult }) {
  const { t } = useTranslation();
  const benches = (r.benchmarks ?? []) as BenchmarkResult[];
  const totals = r.totals;
  const tokens = totals?.tokens;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="border-b text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-2 py-2 text-left">{t("results.title")}</th>
            <th className="px-2 py-2 text-right">{t("results.samples")}</th>
            <th className="px-2 py-2 text-right">{t("results.accuracy")}</th>
            <th className="px-2 py-2 text-right">{t("results.ci95")}</th>
            <th className="px-2 py-2 text-right">{t("results.p50")}</th>
            <th className="px-2 py-2 text-right">{t("results.p95")}</th>
            <th className="px-2 py-2 text-right">{t("results.prompt")}</th>
            <th className="px-2 py-2 text-right">{t("results.completion")}</th>
            <th className="px-2 py-2 text-right">{t("results.reasoning")}</th>
            <th className="px-2 py-2 text-right">{t("results.cost")}</th>
          </tr>
        </thead>
        <tbody>
          {benches.map((b) => (
            <tr key={b.name} className="border-b last:border-b-0">
              <td className="px-2 py-2 font-medium">
                <div className="flex items-center gap-1.5">
                  <span>{b.name}</span>
                  {b.thinking_used && <Badge variant="success">think</Badge>}
                  {b.denominator_policy === "strict" && <Badge variant="outline">strict</Badge>}
                </div>
              </td>
              <td className="px-2 py-2 text-right tabular-nums">{b.samples}</td>
              <td className="px-2 py-2 text-right tabular-nums">{fmtAcc(b.accuracy)}</td>
              <td className="px-2 py-2 text-right tabular-nums text-xs text-muted-foreground">
                [{(b.accuracy_ci95?.[0] ?? 0).toFixed(2)}, {(b.accuracy_ci95?.[1] ?? 0).toFixed(2)}]
              </td>
              <td className="px-2 py-2 text-right tabular-nums">{fmtMs(b.latency_ms?.p50)}</td>
              <td className="px-2 py-2 text-right tabular-nums">{fmtMs(b.latency_ms?.p95)}</td>
              <td className="px-2 py-2 text-right tabular-nums">{fmtNum(b.tokens?.prompt)}</td>
              <td className="px-2 py-2 text-right tabular-nums">{fmtNum(b.tokens?.completion)}</td>
              <td className="px-2 py-2 text-right tabular-nums">{fmtNum(b.tokens?.reasoning)}</td>
              <td className="px-2 py-2 text-right tabular-nums">{fmtCost(b.cost_usd_estimated)}</td>
            </tr>
          ))}
          <tr className="border-t-2 font-semibold">
            <td className="px-2 py-2">{t("results.totals")}</td>
            <td className="px-2 py-2 text-right tabular-nums">
              {benches.reduce((acc, b) => acc + (b.samples ?? 0), 0)}
            </td>
            <td className="px-2 py-2 text-right tabular-nums">{fmtAcc(totals?.accuracy_macro)}</td>
            <td className="px-2 py-2 text-right text-muted-foreground">macro</td>
            <td colSpan={2}></td>
            <td className="px-2 py-2 text-right tabular-nums">{fmtNum(tokens?.prompt)}</td>
            <td className="px-2 py-2 text-right tabular-nums">{fmtNum(tokens?.completion)}</td>
            <td className="px-2 py-2 text-right tabular-nums">{fmtNum(tokens?.reasoning)}</td>
            <td className="px-2 py-2 text-right tabular-nums">{fmtCost(totals?.cost_usd_estimated)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

// Lightweight client-side renderers so the SPA can export without the
// backend. Loose mirrors of `reports/markdown.py` / `reports/html.py`.
function renderRunMd(r: RunResult): string {
  const p = r.provider ?? {};
  const t = r.totals ?? {};
  const lines: string[] = [];
  lines.push(`# evalbox run — ${r.run_id ?? "?"}`);
  lines.push("");
  lines.push(`- **model** \`${p.model ?? "?"}\``);
  lines.push(`- **base_url** \`${p.base_url ?? "?"}\` (adapter \`${p.adapter ?? "?"}\`)`);
  lines.push(`- **macro accuracy** ${(t.accuracy_macro ?? 0).toFixed(4)}`);
  lines.push(`- **total cost** ${t.cost_usd_estimated == null ? "—" : `$${t.cost_usd_estimated.toFixed(4)}`}`);
  lines.push("");
  lines.push("| benchmark | samples | accuracy | cost |");
  lines.push("|---|---:|---:|---:|");
  for (const b of r.benchmarks ?? []) {
    const cost = b.cost_usd_estimated == null ? "—" : `$${b.cost_usd_estimated.toFixed(4)}`;
    lines.push(`| ${b.name} | ${b.samples} | ${(b.accuracy ?? 0).toFixed(4)} | ${cost} |`);
  }
  if (r.messages?.length) {
    lines.push("");
    lines.push("## Messages");
    lines.push("");
    for (const message of r.messages) {
      const at = message.created_at ? ` ${message.created_at}` : "";
      lines.push(`- \`${message.role}\`${at}: ${message.content}`);
    }
  }
  return lines.join("\n") + "\n";
}

function renderRunHtml(r: RunResult): string {
  const md = renderRunMd(r).replace(/&/g, "&amp;").replace(/</g, "&lt;");
  return `<!doctype html><html><head><meta charset="utf-8">
<title>evalbox · ${r.provider?.model ?? "run"}</title>
<style>body{font-family:system-ui,sans-serif;max-width:48em;margin:2em auto;padding:0 1em}
pre{background:#f6f6f6;padding:1em;border-radius:6px;white-space:pre-wrap}</style></head>
<body><pre>${md}</pre></body></html>`;
}
