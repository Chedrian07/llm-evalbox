import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Check,
  CheckCircle2,
  Loader2,
  Plug,
  RefreshCw,
  Search,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import type { ModelInfo } from "@/lib/api";
import { useApp } from "@/lib/store";
import { cn } from "@/lib/cn";

const API_KEY_ENVS = [
  "OPENAI_API_KEY",
  "OPENROUTER_API_KEY",
  "TOGETHER_API_KEY",
  "FIREWORKS_API_KEY",
  "VLLM_KEY",
  "GEMINI_API_KEY",
  "ANTHROPIC_API_KEY",
  "E2B_API_KEY",
];
const MAX_VISIBLE_MODELS = 60;
const ADAPTERS: { v: "auto" | "chat_completions" | "responses"; labelKey: string }[] = [
  { v: "auto", labelKey: "connection.adapter_auto" },
  { v: "chat_completions", labelKey: "connection.adapter_chat" },
  { v: "responses", labelKey: "connection.adapter_responses" },
];

export function ConnectionCard({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation();
  const s = useApp();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [modelFilter, setModelFilter] = useState("");

  useEffect(() => {
    if (!s.hydrated || compact) return;
    const baseUrl = s.baseUrl.trim();
    if (!baseUrl) return;
    const handle = setTimeout(() => void s.loadModels(), 350);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s.hydrated, s.baseUrl, s.adapter, s.apiKey, s.apiKeyEnv, compact]);

  async function test() {
    setBusy(true);
    setErr(null);
    try {
      const r = await api.testConnection({
        base_url: s.baseUrl,
        model: s.model,
        adapter: s.adapter,
        api_key: s.apiKey || undefined,
        api_key_env: s.apiKey ? undefined : s.apiKeyEnv,
      });
      s.setConnResponse(r);
      if (!r.ok) setErr(r.error || "Connection failed");
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  if (compact) {
    return (
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Badge variant={s.conn?.ok ? "success" : "outline"}>
          {s.conn?.ok ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
          <span>{s.adapter}</span>
        </Badge>
        <span className="text-muted-foreground">{s.model}</span>
        <span className="text-muted-foreground/70">@ {hostOnly(s.baseUrl)}</span>
      </div>
    );
  }

  const ok = s.conn?.ok;

  return (
    <section className="overflow-hidden rounded-lg border border-border/60 surface-1">
      {/* Header bar — title on left, status on right */}
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 px-4 py-3">
        <div className="flex items-center gap-2">
          <Plug className="h-4 w-4 text-muted-foreground" />
          <h2 className="text-base font-semibold leading-none">{t("connection.title")}</h2>
          {ok && (
            <Badge variant="outline" className="border-primary/40 bg-primary/10 text-primary">
              <CheckCircle2 className="h-3 w-3" /> {t("connection.ok")}
              {s.conn?.latency_ms != null && (
                <span className="ml-1 font-mono text-[0.65rem] text-primary/80">
                  {Math.round(s.conn.latency_ms)}ms
                </span>
              )}
            </Badge>
          )}
        </div>
        <Button onClick={test} size="sm" disabled={busy || !s.baseUrl || !s.model} className="h-8">
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plug className="h-3.5 w-3.5" />}
          {busy ? t("connection.testing") : t("connection.test")}
        </Button>
      </header>

      <div className="grid gap-3 p-4 lg:grid-cols-2">
        <Field label={t("connection.base_url")}>
          <Input
            value={s.baseUrl}
            placeholder={t("connection.base_url_placeholder")!}
            onChange={(e) => s.setConnection({ baseUrl: e.target.value })}
            spellCheck={false}
            autoComplete="off"
          />
        </Field>

        <Field
          label={t("connection.model")}
          right={<ModelStatusPill />}
        >
          <Input
            value={s.model}
            placeholder={t("connection.model_placeholder")!}
            list="evalbox-model-options"
            autoComplete="off"
            spellCheck={false}
            onChange={(e) => s.setConnection({ model: e.target.value })}
            onFocus={() => {
              if (s.availableModels.length === 0 && !s.modelsLoading) void s.loadModels();
            }}
          />
          <datalist id="evalbox-model-options">
            {s.availableModels.map((m) => (
              <option key={m.id} value={m.id}>
                {m.owned_by ? m.owned_by : ""}
              </option>
            ))}
          </datalist>
        </Field>

        <Field label={t("connection.adapter")}>
          <div role="tablist" className="flex w-full rounded-md border border-input bg-background/50 p-0.5">
            {ADAPTERS.map(({ v, labelKey }) => (
              <button
                key={v}
                type="button"
                role="tab"
                aria-selected={s.adapter === v}
                data-active={s.adapter === v}
                onClick={() => s.setConnection({ adapter: v })}
                className="segmented-item flex-1 px-2 py-1 text-xs"
                title={t(labelKey)}
              >
                {v === "auto" ? "auto" : v === "chat_completions" ? "chat" : "responses"}
              </button>
            ))}
          </div>
        </Field>

        <Field label={t("connection.api_key_env")}>
          <select
            value={s.apiKeyEnv}
            onChange={(e) => s.setConnection({ apiKeyEnv: e.target.value })}
            className="flex h-9 w-full rounded-md border border-input bg-background/50 px-3 py-1 text-sm"
          >
            {API_KEY_ENVS.map((name) => (
              <option key={name} value={name}>
                {name}
                {s.serverApiKeys[name] ? " ✓" : ""}
              </option>
            ))}
          </select>
        </Field>

        <Field
          label={t("connection.api_key")}
          right={
            s.hasServerApiKey && !s.apiKey ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-primary/15 px-2 py-0.5 text-[0.65rem] font-medium text-primary">
                <Check className="h-3 w-3" />
                ${s.apiKeyEnv}
              </span>
            ) : null
          }
          fullWidth
        >
          <Input
            type="password"
            value={s.apiKey}
            placeholder={
              s.hasServerApiKey && !s.apiKey
                ? t("connection.api_key_placeholder_server", { env: s.apiKeyEnv, defaultValue: `(picked up from ${s.apiKeyEnv} on the server — leave blank to use it)` })
                : t("connection.api_key_placeholder")!
            }
            onChange={(e) => s.setConnection({ apiKey: e.target.value })}
          />
        </Field>
      </div>

      {/* Model picker (only renders when /v1/models returned >0) */}
      {s.availableModels.length > 0 && (
        <div className="border-t border-border/60 surface-2/40 p-4">
          <ModelPicker
            models={s.availableModels}
            selectedModel={s.model}
            filter={modelFilter}
            onFilterChange={setModelFilter}
            onSelect={(model) => {
              s.setConnection({ model });
              setModelFilter("");
              setErr(null);
            }}
          />
        </div>
      )}

      {/* Error / capability footer */}
      {(err || s.capability || s.conn?.effective_base_url) && (
        <footer className="border-t border-border/60 px-4 py-3">
          {err && (
            <p className="mb-2 inline-flex items-center gap-1.5 text-sm text-destructive">
              <XCircle className="h-4 w-4" />
              {err.slice(0, 240)}
            </p>
          )}
          {s.conn?.effective_base_url && (
            <div className="mb-2 inline-flex items-center gap-1.5 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[0.7rem] text-amber-300">
              <span className="font-medium">{t("connection.localhost_rewritten")}</span>
              <code className="font-mono opacity-80">{s.conn.effective_base_url}</code>
            </div>
          )}
          {s.capability && (
            <div className="flex flex-wrap gap-1.5">
              <CapabilityBadge ok={s.capability.accepts_temperature} label="temperature" />
              <CapabilityBadge ok={s.capability.accepts_top_p} label="top_p" />
              <CapabilityBadge ok={s.capability.accepts_top_k} label="top_k" />
              <CapabilityBadge ok={s.capability.accepts_seed} label="seed" />
              <CapabilityBadge ok={s.capability.accepts_reasoning_effort} label="reasoning_effort" />
              {s.capability.use_max_completion_tokens && (
                <Badge variant="outline">max_completion_tokens</Badge>
              )}
              {s.conn?.thinking_observed && <Badge variant="success">thinking observed</Badge>}
              {s.conn?.learned_drop_params && s.conn.learned_drop_params.length > 0 && (
                <Badge variant="destructive">drop: {s.conn.learned_drop_params.join(",")}</Badge>
              )}
            </div>
          )}
          {s.capability?.notes && (
            <p className="mt-2 text-xs text-muted-foreground">{s.capability.notes}</p>
          )}
        </footer>
      )}
    </section>
  );
}

function Field({
  label,
  right,
  fullWidth = false,
  children,
}: {
  label: string;
  right?: React.ReactNode;
  fullWidth?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("space-y-1", fullWidth && "lg:col-span-2")}>
      <Label className="flex items-center justify-between text-[0.7rem] uppercase tracking-wide text-muted-foreground">
        <span>{label}</span>
        {right}
      </Label>
      {children}
    </div>
  );
}

function ModelPicker({
  models,
  selectedModel,
  filter,
  onFilterChange,
  onSelect,
}: {
  models: ModelInfo[];
  selectedModel: string;
  filter: string;
  onFilterChange: (value: string) => void;
  onSelect: (model: string) => void;
}) {
  const { t } = useTranslation();
  const loadModels = useApp((s) => s.loadModels);
  const loading = useApp((s) => s.modelsLoading);
  const filteredModels = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const matches = q
      ? models.filter((m) => `${m.id} ${m.owned_by ?? ""}`.toLowerCase().includes(q))
      : models;
    return [...matches].sort((a, b) => {
      if (a.id === selectedModel) return -1;
      if (b.id === selectedModel) return 1;
      return a.id.localeCompare(b.id);
    });
  }, [models, filter, selectedModel]);
  const visibleModels = filteredModels.slice(0, MAX_VISIBLE_MODELS);
  const selectedListed = models.some((m) => m.id === selectedModel);
  const canSearch = models.length > 5;

  if (models.length === 0) return null;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-medium">{t("connection.model_picker_title")}</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {t("connection.model_picker_showing", {
              visible: visibleModels.length,
              total: models.length,
            })}
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => void loadModels({ force: true })}
          disabled={loading}
          className="h-7"
        >
          {loading ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <RefreshCw className="h-3 w-3" />
          )}
          {t("connection.models_refresh")}
        </Button>
      </div>

      {canSearch && (
        <div className="relative mt-3">
          <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={filter}
            placeholder={t("connection.model_picker_search")!}
            onChange={(e) => onFilterChange(e.target.value)}
            className="h-8 pl-7 text-sm"
          />
        </div>
      )}

      {!selectedListed && (
        <div className="mt-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-300">
          {t("connection.model_picker_not_listed", { model: selectedModel })}
        </div>
      )}

      <div className="mt-3 max-h-48 overflow-y-auto pr-1">
        {visibleModels.length === 0 ? (
          <div className="rounded-md border border-dashed border-input px-3 py-4 text-center text-sm text-muted-foreground">
            {t("connection.model_picker_empty")}
          </div>
        ) : (
          <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
            {visibleModels.map((model) => {
              const selected = model.id === selectedModel;
              return (
                <button
                  key={model.id}
                  type="button"
                  onClick={() => onSelect(model.id)}
                  className={cn(
                    "group flex min-w-0 items-center justify-between gap-2 rounded-md border px-2.5 py-1.5 text-left text-sm transition",
                    selected
                      ? "border-primary/60 bg-primary/10 text-foreground"
                      : "border-border/50 bg-background/40 hover:border-border hover:bg-accent/40",
                  )}
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-mono text-[0.78rem]">{model.id}</span>
                    {model.owned_by && (
                      <span className="block truncate text-[0.65rem] text-muted-foreground">
                        {model.owned_by}
                      </span>
                    )}
                  </span>
                  {selected && <Check className="h-3.5 w-3.5 shrink-0 text-primary" />}
                </button>
              );
            })}
          </div>
        )}
        {filteredModels.length > visibleModels.length && (
          <div className="px-2 pt-2 text-xs text-muted-foreground">
            {t("connection.model_picker_more", {
              hidden: filteredModels.length - visibleModels.length,
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function CapabilityBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "border-border/40",
        ok
          ? "bg-primary/10 text-primary"
          : "bg-muted/40 text-muted-foreground line-through decoration-muted-foreground/40",
      )}
    >
      {label}
    </Badge>
  );
}

function ModelStatusPill() {
  const { t } = useTranslation();
  const loading = useApp((s) => s.modelsLoading);
  const error = useApp((s) => s.modelsError);
  const count = useApp((s) => s.availableModels.length);
  const loadModels = useApp((s) => s.loadModels);

  if (loading) {
    return (
      <span className="inline-flex items-center gap-1 text-[0.65rem] font-normal normal-case tracking-normal text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
        {t("connection.models_loading")}
      </span>
    );
  }
  if (error) {
    return (
      <span
        className="text-[0.65rem] font-normal normal-case tracking-normal text-amber-400"
        title={error}
      >
        {t("connection.models_error")}
      </span>
    );
  }
  if (count > 0) {
    return (
      <span className="inline-flex items-center gap-1 text-[0.65rem] font-normal normal-case tracking-normal text-muted-foreground">
        {t("connection.models_count", { count })}
        <button
          type="button"
          onClick={() => void loadModels({ force: true })}
          className="inline-flex items-center text-muted-foreground/70 transition hover:text-foreground"
          title={t("connection.models_refresh")!}
          aria-label={t("connection.models_refresh")!}
        >
          <RefreshCw className="h-3 w-3" />
        </button>
      </span>
    );
  }
  return null;
}

function hostOnly(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}
