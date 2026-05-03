// SPDX-License-Identifier: Apache-2.0
// Global app state: connection config, selected benches, run lifecycle.

import { create } from "zustand";
import type { CapabilityInfo, ConnectionResponse, ServerDefaults } from "./api";

export type Stage = "setup" | "running" | "results";

export interface BenchProgress {
  bench: string;
  current: number;
  total: number;
  running_accuracy: number;
  thinking_used: boolean;
  done: boolean;
  result?: any;
}

interface AppState {
  // Connection
  baseUrl: string;
  model: string;
  adapter: "auto" | "chat_completions" | "responses";
  apiKey: string;
  apiKeyEnv: string;
  conn: ConnectionResponse | null;
  capability: CapabilityInfo | null;
  /** True when the server says an API key is available in env — the SPA can
      hide the key input and the backend resolves it server-side per request. */
  hasServerApiKey: boolean;
  /** True once we have either tried hydrating from /api/defaults or accepted
      the fallback defaults — used to delay first paint of the connection card. */
  hydrated: boolean;
  setConnection: (patch: Partial<Pick<AppState, "baseUrl" | "model" | "adapter" | "apiKey" | "apiKeyEnv">>) => void;
  setConnResponse: (resp: ConnectionResponse) => void;
  hydrateFromServer: (d: ServerDefaults) => void;

  // Setup
  selectedBenches: Set<string>;
  toggleBench: (name: string) => void;
  samples: number;
  setSamples: (n: number) => void;
  concurrency: number;
  setConcurrency: (n: number) => void;
  thinking: "auto" | "on" | "off";
  setThinking: (t: "auto" | "on" | "off") => void;
  acceptCodeExec: boolean;
  setAcceptCodeExec: (b: boolean) => void;
  strictFailures: boolean;
  setStrictFailures: (b: boolean) => void;
  maxCostUsd: number | null;
  setMaxCostUsd: (n: number | null) => void;

  // Run lifecycle
  stage: Stage;
  setStage: (s: Stage) => void;
  runId: string | null;
  setRunId: (id: string | null) => void;
  benchProgress: Record<string, BenchProgress>;
  resetBenchProgress: () => void;
  updateBenchProgress: (b: string, patch: Partial<BenchProgress>) => void;
  finalResult: any | null;
  setFinalResult: (r: any | null) => void;
}

const detectDefaultBaseUrl = (): string => {
  // Try to read EVALBOX_BASE_URL via a meta tag if the host injected one.
  if (typeof document !== "undefined") {
    const m = document.querySelector('meta[name="evalbox-base-url"]')?.getAttribute("content");
    if (m) return m;
  }
  return "https://api.openai.com/v1";
};

export const useApp = create<AppState>((set) => ({
  baseUrl: detectDefaultBaseUrl(),
  model: "gpt-4o-mini",
  adapter: "auto",
  apiKey: "",
  apiKeyEnv: "OPENAI_API_KEY",
  conn: null,
  capability: null,
  hasServerApiKey: false,
  hydrated: false,
  setConnection: (patch) => set(patch),
  setConnResponse: (resp) =>
    set({ conn: resp, capability: resp.capability }),
  hydrateFromServer: (d) =>
    set((prev) => ({
      // Each field: prefer the server-supplied value, fall back to the
      // existing default. We don't override values the user has already
      // typed (initial mount only).
      baseUrl: d.base_url ?? prev.baseUrl,
      model: d.model ?? prev.model,
      adapter: (d.adapter as AppState["adapter"]) ?? prev.adapter,
      apiKeyEnv: d.api_key_env ?? prev.apiKeyEnv,
      thinking: ((d.thinking as AppState["thinking"]) ?? prev.thinking),
      concurrency: d.concurrency ?? prev.concurrency,
      maxCostUsd: d.max_cost_usd ?? prev.maxCostUsd,
      acceptCodeExec: d.accept_code_exec || prev.acceptCodeExec,
      hasServerApiKey: d.has_api_key,
      hydrated: true,
    })),

  selectedBenches: new Set(["mmlu"]),
  toggleBench: (name) =>
    set((s) => {
      const next = new Set(s.selectedBenches);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return { selectedBenches: next };
    }),
  samples: 50,
  setSamples: (n) => set({ samples: n }),
  concurrency: 8,
  setConcurrency: (n) => set({ concurrency: n }),
  thinking: "auto",
  setThinking: (t) => set({ thinking: t }),
  acceptCodeExec: false,
  setAcceptCodeExec: (b) => set({ acceptCodeExec: b }),
  strictFailures: false,
  setStrictFailures: (b) => set({ strictFailures: b }),
  maxCostUsd: 5.0,
  setMaxCostUsd: (n) => set({ maxCostUsd: n }),

  stage: "setup",
  setStage: (s) => set({ stage: s }),
  runId: null,
  setRunId: (id) => set({ runId: id }),
  benchProgress: {},
  resetBenchProgress: () => set({ benchProgress: {} }),
  updateBenchProgress: (b, patch) =>
    set((s) => ({
      benchProgress: {
        ...s.benchProgress,
        [b]: {
          ...{ bench: b, current: 0, total: 0, running_accuracy: 0, thinking_used: false, done: false },
          ...s.benchProgress[b],
          ...patch,
        },
      },
    })),
  finalResult: null,
  setFinalResult: (r) => set({ finalResult: r }),
}));
