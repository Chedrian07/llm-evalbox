import { useState } from "react";

import { BenchmarkGrid } from "@/components/benchmark-grid";
import { ConnectionCard } from "@/components/connection-card";
import { RunPanel } from "@/components/run-panel";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";

export function SetupPage() {
  const s = useApp();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

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
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="min-w-0 space-y-4">
        <ConnectionCard />
        <BenchmarkGrid />
      </div>
      <RunPanel onStart={start} busy={busy} err={err} />
    </div>
  );
}
