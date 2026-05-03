// SPDX-License-Identifier: Apache-2.0
// Thin fetch wrappers for the FastAPI backend. All paths are same-origin
// (the SPA is served by the same FastAPI server in production).

export interface ConnectionRequest {
  base_url: string;
  model: string;
  adapter?: string;
  api_key?: string;
  api_key_env?: string;
  extra_headers?: Record<string, string>;
}

export interface CapabilityInfo {
  accepts_temperature: boolean;
  accepts_top_p: boolean;
  accepts_top_k: boolean;
  accepts_seed: boolean;
  accepts_reasoning_effort: boolean;
  use_max_completion_tokens: boolean;
  notes: string;
}

export interface ConnectionResponse {
  ok: boolean;
  adapter: string;
  model_listed: boolean | null;
  model_count: number | null;
  latency_ms: number | null;
  finish_reason: string | null;
  thinking_observed: boolean | null;
  text_preview: string | null;
  capability: CapabilityInfo;
  learned_drop_params: string[];
  error: string | null;
}

export interface BenchmarkInfo {
  name: string;
  quick_size: number;
  is_code_bench: boolean;
  category: string;
  license: string | null;
}

export interface PricingEstimate {
  est_prompt_tokens: number;
  est_completion_tokens: number;
  est_reasoning_tokens: number;
  est_cost_usd: number | null;
  est_seconds: number;
}

export interface RunCreateRequest {
  connection: ConnectionRequest;
  benches: string[];
  samples?: number;
  concurrency?: number;
  thinking?: "auto" | "on" | "off";
  no_thinking_rerun?: boolean;
  prompt_cache_aware?: boolean;
  accept_code_exec?: boolean;
  strict_failures?: boolean;
  no_cache?: boolean;
  max_cost_usd?: number | null;
  sampling?: {
    temperature?: number | null;
    top_p?: number | null;
    top_k?: number | null;
    max_tokens?: number | null;
    reasoning_effort?: string | null;
  };
  drop_params?: string[];
}

export interface BenchmarkResult {
  name: string;
  samples: number;
  accuracy: number;
  accuracy_ci95?: [number, number] | number[];
  correct_count?: number;
  category_scores?: Record<string, number>;
  error_breakdown?: Record<string, number>;
  latency_ms?: { p50?: number | null; p95?: number | null };
  tokens?: {
    prompt?: number;
    completion?: number;
    reasoning?: number;
    cached_prompt?: number;
    reasoning_estimated?: boolean;
  };
  cost_usd?: number | null;
  cost_usd_estimated?: number | null;
  duration_s?: number;
  thinking_used?: boolean;
  denominator_policy?: "lenient" | "strict" | string;
  cache_hits?: number;
  prompt_cache_hit_rate?: number;
  learned_drop_params?: string[];
}

export interface RunResult {
  schema_version: number;
  run_id: string;
  started_at: string;
  finished_at: string;
  seed: number;
  provider?: { adapter?: string; base_url?: string; model?: string };
  sampling?: Record<string, unknown>;
  thinking?: { mode?: string; used?: boolean };
  capability?: Record<string, unknown>;
  strict_deterministic?: boolean;
  strict_failures?: boolean;
  benchmarks?: BenchmarkResult[];
  totals?: {
    accuracy_macro?: number;
    tokens?: {
      prompt?: number;
      completion?: number;
      reasoning?: number;
      cached_prompt?: number;
    };
    cost_usd_estimated?: number | null;
  };
}

export interface RunDetail {
  run_id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  result: RunResult | null;
}

export interface HistorySummary {
  run_id: string;
  started_at: string;
  finished_at: string | null;
  model: string | null;
  base_url: string | null;
  adapter: string | null;
  accuracy_macro: number | null;
  cost_usd: number | null;
  bench_count: number;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`HTTP ${r.status}: ${text || r.statusText}`);
  }
  return r.json() as Promise<T>;
}

export interface ServerDefaults {
  base_url: string | null;
  model: string | null;
  adapter: string | null;
  profile: string | null;
  thinking: string | null;
  reasoning_effort: string | null;
  concurrency: number | null;
  rpm: number | null;
  tpm: number | null;
  max_cost_usd: number | null;
  accept_code_exec: boolean;
  no_cache: boolean;
  strict_failures: boolean;
  no_thinking_rerun: boolean;
  prompt_cache_aware: boolean;
  drop_params: string | null;
  api_key_env: string;
  has_api_key: boolean;
  detected_api_key_envs: string[];
  api_keys: Record<string, boolean>;
}

export interface ModelInfo {
  id: string;
  owned_by: string | null;
  created: number | null;
}

export const api = {
  health: () => request<{ status: string; version: string }>("/api/health"),
  defaults: () => request<ServerDefaults>("/api/defaults"),
  benchmarks: () => request<BenchmarkInfo[]>("/api/benchmarks"),
  listModels: (
    args: { base_url: string; model?: string; adapter?: string; api_key?: string; api_key_env?: string },
    init?: RequestInit,
  ) =>
    request<ModelInfo[]>("/api/models", {
      method: "POST",
      body: JSON.stringify({
        base_url: args.base_url,
        model: args.model || "",
        adapter: args.adapter,
        api_key: args.api_key || undefined,
        api_key_env: args.api_key ? undefined : args.api_key_env,
      }),
      ...init,
    }),
  testConnection: (req: ConnectionRequest) =>
    request<ConnectionResponse>("/api/connection/test", {
      method: "POST",
      body: JSON.stringify(req),
    }),
  estimateCost: (
    model: string,
    benchmarks: string[],
    samples: number,
    concurrency: number,
    thinking: "auto" | "on" | "off",
  ) =>
    request<PricingEstimate>("/api/pricing/estimate", {
      method: "POST",
      body: JSON.stringify({ model, benchmarks, samples, concurrency, thinking }),
    }),
  startRun: (req: RunCreateRequest) =>
    request<{ run_id: string; status: string }>("/api/runs", {
      method: "POST",
      body: JSON.stringify(req),
    }),
  getRun: (id: string) => request<RunDetail>(`/api/runs/${id}`),
  cancelRun: (id: string) =>
    request<{ status: string }>(`/api/runs/${id}`, { method: "DELETE" }),
  history: (limit = 100) => request<HistorySummary[]>(`/api/history?limit=${limit}`),
  getHistory: (id: string) => request<RunResult>(`/api/history/${encodeURIComponent(id)}`),
  deleteHistory: (id: string) =>
    request<{ status: string }>(`/api/history/${encodeURIComponent(id)}`, { method: "DELETE" }),
  clearHistory: () => request<{ deleted: number }>("/api/history", { method: "DELETE" }),
  shareRun: (runId: string) =>
    request<{ hash: string; url: string }>("/api/shares", {
      method: "POST",
      body: JSON.stringify({ run_id: runId }),
    }),
};
