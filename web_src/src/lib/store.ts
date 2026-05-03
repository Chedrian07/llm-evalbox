// SPDX-License-Identifier: Apache-2.0
// Global app state: connection config, selected benches, run lifecycle.

import { create } from "zustand";
import { api } from "./api";
import type {
  BenchmarkResult,
  CapabilityInfo,
  ConnectionResponse,
  ModelInfo,
  RunResult,
  ServerDefaults,
} from "./api";

export type Stage = "setup" | "running" | "results";

export interface BenchProgress {
  bench: string;
  current: number;
  total: number;
  running_accuracy: number;
  thinking_used: boolean;
  done: boolean;
  result?: BenchmarkResult;
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
  /** True when the server says an API key is available in env for the
      currently selected `apiKeyEnv` — the SPA can hide the key input and
      the backend resolves it server-side per request. */
  hasServerApiKey: boolean;
  /** Per-env key availability snapshot from /api/defaults — keeps the
      "key picked up" hint accurate when the user switches `apiKeyEnv`. */
  serverApiKeys: Record<string, boolean>;
  /** True once we have either tried hydrating from /api/defaults or accepted
      the fallback defaults — used to delay first paint of the connection card. */
  hydrated: boolean;
  setConnection: (patch: Partial<Pick<AppState, "baseUrl" | "model" | "adapter" | "apiKey" | "apiKeyEnv">>) => void;
  setConnResponse: (resp: ConnectionResponse) => void;
  hydrateFromServer: (d: ServerDefaults) => void;

  // Model discovery (proxy to GET /v1/models on the configured endpoint)
  availableModels: ModelInfo[];
  modelsLoading: boolean;
  /** Last error from /api/models — most gateways without /v1/models surface
      a 502 here; we keep the input free-typing so users can still set a model. */
  modelsError: string | null;
  /** Tuple of inputs the last successful list was fetched for — lets us skip
      redundant fetches when the user types but hasn't changed the connection. */
  modelsKey: string | null;
  loadModels: (opts?: { force?: boolean }) => Promise<void>;

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
  noThinkingRerun: boolean;
  setNoThinkingRerun: (b: boolean) => void;
  promptCacheAware: boolean;
  setPromptCacheAware: (b: boolean) => void;
  reasoningEffort: string | null;
  setReasoningEffort: (s: string | null) => void;
  noCache: boolean;
  setNoCache: (b: boolean) => void;
  dropParams: string;
  setDropParams: (s: string) => void;
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
  finalResult: RunResult | null;
  setFinalResult: (r: RunResult | null) => void;
}

// Module-level token so concurrent loadModels() calls cancel earlier in-flights.
// (AbortController would also work; this is simpler since fetch() in api.ts
// doesn't take a signal yet and we only need "ignore stale results".)
let _modelsLoadToken = 0;

const detectDefaultBaseUrl = (): string => {
  // Try to read EVALBOX_BASE_URL via a meta tag if the host injected one.
  if (typeof document !== "undefined") {
    const m = document.querySelector('meta[name="evalbox-base-url"]')?.getAttribute("content");
    if (m) return m;
  }
  return "https://api.openai.com/v1";
};

export const useApp = create<AppState>((set, get) => ({
  baseUrl: detectDefaultBaseUrl(),
  model: "gpt-4o-mini",
  adapter: "auto",
  apiKey: "",
  apiKeyEnv: "OPENAI_API_KEY",
  conn: null,
  capability: null,
  hasServerApiKey: false,
  serverApiKeys: {},
  hydrated: false,
  availableModels: [],
  modelsLoading: false,
  modelsError: null,
  modelsKey: null,
  loadModels: async (opts) => {
    const s = get();
    const baseUrl = s.baseUrl.trim();
    if (!baseUrl) {
      set({ availableModels: [], modelsError: null, modelsKey: null });
      return;
    }
    const key = `${baseUrl}|${s.adapter}|${s.apiKey ? "direct" : s.apiKeyEnv}`;
    if (!opts?.force && key === s.modelsKey && s.availableModels.length > 0) return;
    const token = ++_modelsLoadToken;
    set({ modelsLoading: true, modelsError: null });
    try {
      const list = await api.listModels({
        base_url: baseUrl,
        model: s.model,
        adapter: s.adapter,
        api_key: s.apiKey || undefined,
        api_key_env: s.apiKeyEnv,
      });
      if (token !== _modelsLoadToken) return; // stale
      set({ availableModels: list, modelsLoading: false, modelsKey: key });
    } catch (e: any) {
      if (token !== _modelsLoadToken) return;
      set({
        availableModels: [],
        modelsLoading: false,
        modelsError: e?.message?.slice(0, 200) || "list_models failed",
        modelsKey: null,
      });
    }
  },
  setConnection: (patch) =>
    set((prev) => {
      const next: Partial<AppState> = { ...patch };
      const connectionChanged = (
        ["baseUrl", "model", "adapter", "apiKey", "apiKeyEnv"] as const
      ).some((key) => patch[key] !== undefined && patch[key] !== prev[key]);
      // When the user switches the env-var selector, recompute hasServerApiKey
      // from the snapshot we got at mount. Without this the badge can show
      // "key picked up" for an env var that isn't actually set.
      if (patch.apiKeyEnv && prev.serverApiKeys) {
        next.hasServerApiKey = !!prev.serverApiKeys[patch.apiKeyEnv];
      }
      if (connectionChanged) {
        next.conn = null;
        next.capability = null;
      }
      return next;
    }),
  setConnResponse: (resp) =>
    set({ conn: resp, capability: resp.capability }),
  hydrateFromServer: (d) =>
    set((prev) => {
      // Mount-time only: don't overwrite user edits if hydrate runs twice
      // (e.g. React StrictMode double-effect or HMR). The App.tsx guard
      // also blocks the second call, but we belt-and-suspenders here.
      if (prev.hydrated) return {};
      return {
        baseUrl: d.base_url ?? prev.baseUrl,
        model: d.model ?? prev.model,
        adapter: (d.adapter as AppState["adapter"]) ?? prev.adapter,
        apiKeyEnv: d.api_key_env ?? prev.apiKeyEnv,
        thinking: ((d.thinking as AppState["thinking"]) ?? prev.thinking),
        reasoningEffort: d.reasoning_effort ?? prev.reasoningEffort,
        concurrency: d.concurrency ?? prev.concurrency,
        maxCostUsd: d.max_cost_usd ?? prev.maxCostUsd,
        acceptCodeExec: d.accept_code_exec ?? prev.acceptCodeExec,
        noCache: d.no_cache ?? prev.noCache,
        strictFailures: d.strict_failures ?? prev.strictFailures,
        noThinkingRerun: d.no_thinking_rerun ?? prev.noThinkingRerun,
        promptCacheAware: d.prompt_cache_aware ?? prev.promptCacheAware,
        dropParams: d.drop_params ?? prev.dropParams,
        hasServerApiKey: d.has_api_key,
        serverApiKeys: d.api_keys ?? {},
        hydrated: true,
      };
    }),

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
  noThinkingRerun: false,
  setNoThinkingRerun: (b) => set({ noThinkingRerun: b }),
  promptCacheAware: false,
  setPromptCacheAware: (b) => set({ promptCacheAware: b }),
  reasoningEffort: null,
  setReasoningEffort: (s) => set({ reasoningEffort: s }),
  noCache: false,
  setNoCache: (b) => set({ noCache: b }),
  dropParams: "",
  setDropParams: (s) => set({ dropParams: s }),
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
