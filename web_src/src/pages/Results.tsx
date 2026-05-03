import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConnectionCard } from "@/components/connection-card";
import { useApp } from "@/lib/store";
import { fmtAcc, fmtCost, fmtMs, fmtNum } from "@/lib/format";

export function ResultsPage() {
  const { t } = useTranslation();
  const s = useApp();
  const [tab, setTab] = useState<"matrix" | "raw">("matrix");

  const r = s.finalResult;

  return (
    <div className="space-y-4">
      <ConnectionCard compact />
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>{t("results.title")}</span>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant={tab === "matrix" ? "default" : "ghost"}
                onClick={() => setTab("matrix")}
              >
                {t("results.matrix")}
              </Button>
              <Button
                size="sm"
                variant={tab === "raw" ? "default" : "ghost"}
                onClick={() => setTab("raw")}
              >
                {t("results.raw")}
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
          {!r ? (
            <p className="text-sm text-muted-foreground">…</p>
          ) : tab === "matrix" ? (
            <Matrix r={r} />
          ) : (
            <pre className="overflow-auto rounded-md bg-muted p-3 text-xs leading-relaxed">
              {JSON.stringify(r, null, 2)}
            </pre>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Matrix({ r }: { r: any }) {
  const { t } = useTranslation();
  const benches = (r.benchmarks ?? []) as any[];
  const totals = r.totals ?? {};

  return (
    <div className="space-y-4 overflow-x-auto">
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
          {benches.map((b: any) => (
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
            <td className="px-2 py-2 text-right tabular-nums">{fmtAcc(totals.accuracy_macro)}</td>
            <td className="px-2 py-2 text-right text-muted-foreground">macro</td>
            <td colSpan={2}></td>
            <td className="px-2 py-2 text-right tabular-nums">{fmtNum(totals.tokens?.prompt)}</td>
            <td className="px-2 py-2 text-right tabular-nums">{fmtNum(totals.tokens?.completion)}</td>
            <td className="px-2 py-2 text-right tabular-nums">{fmtNum(totals.tokens?.reasoning)}</td>
            <td className="px-2 py-2 text-right tabular-nums">{fmtCost(totals.cost_usd_estimated)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
