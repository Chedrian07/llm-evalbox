import { useTranslation } from "react-i18next";
import { Play } from "lucide-react";
import { useState } from "react";

import { BenchmarkGrid } from "@/components/benchmark-grid";
import { ConnectionCard } from "@/components/connection-card";
import { CostPreview } from "@/components/cost-preview";
import { OptionsCard } from "@/components/options-card";
import { ThinkingToggle } from "@/components/thinking-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";

export function SetupPage() {
  const { t } = useTranslation();
  const s = useApp();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const codeBenchSelected = [...s.selectedBenches].some((n) =>
    ["humaneval", "mbpp", "livecodebench"].includes(n),
  );
  const codeBlocked = codeBenchSelected && !s.acceptCodeExec;
  const noBenches = s.selectedBenches.size === 0;
  const blocked = noBenches || codeBlocked;

  async function start() {
    setBusy(true);
    setErr(null);
    s.resetBenchProgress();
    s.setFinalResult(null);
    try {
      const dropParams = s.dropParams
        .split(",")
        .map((p) => p.trim())
        .filter(Boolean);
      const r = await api.startRun({
        connection: {
          base_url: s.baseUrl,
          model: s.model,
          adapter: s.adapter,
          api_key: s.apiKey || undefined,
          api_key_env: s.apiKey ? undefined : s.apiKeyEnv,
        },
        benches: [...s.selectedBenches],
        samples: s.samples,
        concurrency: s.concurrency,
        thinking: s.thinking,
        no_thinking_rerun: s.noThinkingRerun,
        prompt_cache_aware: s.promptCacheAware,
        accept_code_exec: s.acceptCodeExec,
        strict_failures: s.strictFailures,
        no_cache: s.noCache,
        max_cost_usd: s.maxCostUsd ?? null,
        sampling: s.reasoningEffort ? { reasoning_effort: s.reasoningEffort } : undefined,
        drop_params: dropParams,
      });
      s.setRunId(r.run_id);
      s.setStage("running");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
      <div className="space-y-4">
        <ConnectionCard />
        <ThinkingToggle />
        <BenchmarkGrid />
      </div>
      <div className="space-y-4">
        <OptionsCard />
        <CostPreview />
        <RunPlanCard />
        <Button
          size="lg"
          onClick={start}
          disabled={blocked || busy || !s.baseUrl.trim() || !s.model.trim()}
          className="w-full"
        >
          <Play className="h-4 w-4" />
          {busy ? t("run.starting") : t("run.start")}
        </Button>
        {err && <p className="text-xs text-destructive">{err}</p>}
        {noBenches && (
          <p className="text-xs text-muted-foreground">{t("run.no_benches")}</p>
        )}
        {codeBlocked && (
          <p className="text-xs text-destructive">{t("run.code_consent_required")}</p>
        )}
      </div>
    </div>
  );
}

function RunPlanCard() {
  const { t } = useTranslation();
  const s = useApp();
  const selected = [...s.selectedBenches];
  const sampleLabel = s.samples === 0 ? t("benches.full_set") : s.samples.toLocaleString();
  const activeFlags = [
    s.noCache ? t("options.no_cache_short") : null,
    s.promptCacheAware ? t("options.prompt_cache_short") : null,
    s.strictFailures ? t("options.strict_short") : null,
    s.noThinkingRerun ? t("options.no_rerun_short") : null,
    s.reasoningEffort ? `reasoning=${s.reasoningEffort}` : null,
  ].filter(Boolean);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("plan.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="grid grid-cols-2 gap-2">
          <PlanMetric label={t("plan.benchmarks")} value={selected.length.toLocaleString()} />
          <PlanMetric label={t("plan.samples")} value={String(sampleLabel)} />
          <PlanMetric label={t("plan.concurrency")} value={s.concurrency.toLocaleString()} />
          <PlanMetric label={t("plan.thinking")} value={s.thinking} />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {activeFlags.length === 0 ? (
            <span className="text-xs text-muted-foreground">{t("plan.default_flags")}</span>
          ) : (
            activeFlags.map((flag) => (
              <Badge key={flag} variant="outline">
                {flag}
              </Badge>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function PlanMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-input p-2">
      <div className="text-[0.7rem] uppercase text-muted-foreground">{label}</div>
      <div className="mt-1 font-mono text-sm">{value}</div>
    </div>
  );
}
