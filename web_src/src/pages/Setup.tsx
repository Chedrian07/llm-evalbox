import { useTranslation } from "react-i18next";
import { Play } from "lucide-react";

import { BenchmarkGrid } from "@/components/benchmark-grid";
import { ConnectionCard } from "@/components/connection-card";
import { CostPreview } from "@/components/cost-preview";
import { OptionsCard } from "@/components/options-card";
import { ThinkingToggle } from "@/components/thinking-toggle";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";

export function SetupPage() {
  const { t } = useTranslation();
  const s = useApp();

  const codeBenchSelected = [...s.selectedBenches].some((n) =>
    ["humaneval", "mbpp", "livecodebench"].includes(n),
  );
  const codeBlocked = codeBenchSelected && !s.acceptCodeExec;
  const noBenches = s.selectedBenches.size === 0;
  const blocked = noBenches || codeBlocked;

  async function start() {
    s.resetBenchProgress();
    s.setFinalResult(null);
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
      accept_code_exec: s.acceptCodeExec,
      strict_failures: s.strictFailures,
      max_cost_usd: s.maxCostUsd ?? null,
    });
    s.setRunId(r.run_id);
    s.setStage("running");
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
        <Button
          size="lg"
          onClick={start}
          disabled={blocked}
          className="w-full"
        >
          <Play className="h-4 w-4" />
          {t("run.start")}
        </Button>
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
