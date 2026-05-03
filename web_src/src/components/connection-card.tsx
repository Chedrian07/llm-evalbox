import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Check, CheckCircle2, Loader2, RefreshCw, Search, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

export function ConnectionCard({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation();
  const s = useApp();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [modelFilter, setModelFilter] = useState("");

  // Auto-fetch the model list whenever connection inputs settle (debounced).
  // This gives users a native datalist autocomplete instead of having to type
  // the full model name. Gateways that don't expose /v1/models surface an
  // error and we keep the input free-typing.
  useEffect(() => {
    if (!s.hydrated) return;
    if (compact) return;
    const baseUrl = s.baseUrl.trim();
    if (!baseUrl) return;
    const handle = setTimeout(() => {
      void s.loadModels();
    }, 350);
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

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("connection.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label>{t("connection.base_url")}</Label>
            <Input
              value={s.baseUrl}
              placeholder={t("connection.base_url_placeholder")!}
              onChange={(e) => s.setConnection({ baseUrl: e.target.value })}
            />
          </div>
          <div className="space-y-1">
            <Label className="flex items-center justify-between">
              <span>{t("connection.model")}</span>
              <ModelStatusPill />
            </Label>
            <Input
              value={s.model}
              placeholder={t("connection.model_placeholder")!}
              list="evalbox-model-options"
              autoComplete="off"
              spellCheck={false}
              onChange={(e) => s.setConnection({ model: e.target.value })}
              onFocus={() => {
                // Refresh on focus if we never loaded — covers the case where
                // hydration finished after the initial debounce window.
                if (s.availableModels.length === 0 && !s.modelsLoading) {
                  void s.loadModels();
                }
              }}
            />
            <datalist id="evalbox-model-options">
              {s.availableModels.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.owned_by ? `${m.owned_by}` : ""}
                </option>
              ))}
            </datalist>
          </div>
          <div className="space-y-1">
            <Label>{t("connection.adapter")}</Label>
            <select
              value={s.adapter}
              onChange={(e) => s.setConnection({ adapter: e.target.value as typeof s.adapter })}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            >
              <option value="auto">{t("connection.adapter_auto")}</option>
              <option value="chat_completions">{t("connection.adapter_chat")}</option>
              <option value="responses">{t("connection.adapter_responses")}</option>
            </select>
          </div>
          <div className="space-y-1">
            <Label>{t("connection.api_key_env")}</Label>
            <select
              value={s.apiKeyEnv}
              onChange={(e) => s.setConnection({ apiKeyEnv: e.target.value })}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            >
              {API_KEY_ENVS.map((name) => (
                <option key={name} value={name}>
                  {name}{s.serverApiKeys[name] ? " ✓" : ""}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <Label className="flex items-center justify-between">
              <span>{t("connection.api_key")}</span>
              {s.hasServerApiKey && !s.apiKey && (
                <span className="text-[0.7rem] font-normal text-emerald-500">
                  {"✓ $"}{s.apiKeyEnv}
                </span>
              )}
            </Label>
            <Input
              type="password"
              value={s.apiKey}
              placeholder={
                s.hasServerApiKey && !s.apiKey
                  ? `(picked up from ${s.apiKeyEnv} on the server — leave blank to use it)`
                  : t("connection.api_key_placeholder")!
              }
              onChange={(e) => s.setConnection({ apiKey: e.target.value })}
            />
          </div>
        </div>

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

        <div className="flex items-center gap-3">
          <Button onClick={test} disabled={busy || !s.baseUrl || !s.model}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {busy ? t("connection.testing") : t("connection.test")}
          </Button>
          {s.conn?.ok && (
            <span className="text-sm text-emerald-500 inline-flex items-center gap-1">
              <CheckCircle2 className="h-4 w-4" /> {t("connection.ok")}
              {s.conn.latency_ms != null && (
                <span className="text-muted-foreground">
                  {" · "}
                  {t("connection.latency", { ms: Math.round(s.conn.latency_ms) })}
                </span>
              )}
            </span>
          )}
          {err && (
            <span className="text-sm text-destructive inline-flex items-center gap-1">
              <XCircle className="h-4 w-4" /> {err.slice(0, 200)}
            </span>
          )}
        </div>

        {s.capability && (
          <div className="flex flex-wrap gap-2 pt-2">
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
              <Badge variant="destructive">
                drop: {s.conn.learned_drop_params.join(",")}
              </Badge>
            )}
          </div>
        )}
        {s.capability?.notes && (
          <p className="text-xs text-muted-foreground">{s.capability.notes}</p>
        )}
      </CardContent>
    </Card>
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
      ? models.filter((m) =>
          `${m.id} ${m.owned_by ?? ""}`.toLowerCase().includes(q),
        )
      : models;
    return [...matches].sort((a, b) => {
      if (a.id === selectedModel) return -1;
      if (b.id === selectedModel) return 1;
      return a.id.localeCompare(b.id);
    });
  }, [models, filter, selectedModel]);
  const visibleModels = filteredModels.slice(0, MAX_VISIBLE_MODELS);
  const selectedListed = models.some((m) => m.id === selectedModel);

  const selectValue = selectedListed ? selectedModel : "";
  const canSearch = models.length > 5;

  if (models.length === 0) return null;

  return (
    <div className="rounded-md border border-input bg-muted/20 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-sm font-medium">{t("connection.model_picker_title")}</div>
          <div className="mt-0.5 text-xs text-muted-foreground">
            {t("connection.model_picker_showing", {
              visible: visibleModels.length,
              total: models.length,
            })}
          </div>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => void loadModels({ force: true })}
          disabled={loading}
        >
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          {t("connection.models_refresh")}
        </Button>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-[minmax(0,1fr)_minmax(220px,0.55fr)]">
        <div className="space-y-1">
          <Label>{t("connection.model_picker_select")}</Label>
          <select
            value={selectValue}
            onChange={(e) => {
              if (e.target.value) onSelect(e.target.value);
            }}
            className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
          >
            <option value="" disabled>
              {selectedListed
                ? t("connection.model_picker_select")
                : t("connection.model_picker_manual")}
            </option>
            {models.map((model) => (
              <option key={model.id} value={model.id}>
                {model.id}{model.owned_by ? ` (${model.owned_by})` : ""}
              </option>
            ))}
          </select>
        </div>
        {canSearch && (
          <div className="space-y-1">
            <Label>{t("connection.model_picker_search_label")}</Label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                value={filter}
                placeholder={t("connection.model_picker_search")!}
                onChange={(e) => onFilterChange(e.target.value)}
                className="h-9 pl-7 text-sm"
              />
            </div>
          </div>
        )}
      </div>

      {!selectedListed && (
        <div className="mt-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1.5 text-xs text-amber-500">
          {t("connection.model_picker_not_listed", { model: selectedModel })}
        </div>
      )}

      <div className="mt-3 max-h-64 overflow-y-auto pr-1">
        {visibleModels.length === 0 ? (
          <div className="rounded-md border border-dashed border-input px-3 py-4 text-sm text-muted-foreground">
            {t("connection.model_picker_empty")}
          </div>
        ) : (
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {visibleModels.map((model) => {
              const selected = model.id === selectedModel;
              return (
                <button
                  key={model.id}
                  type="button"
                  onClick={() => onSelect(model.id)}
                  className={cn(
                    "flex min-h-14 w-full items-center justify-between gap-3 rounded-md border px-3 py-2 text-left text-sm transition",
                    "hover:border-primary/40 hover:bg-accent hover:text-accent-foreground",
                    selected
                      ? "border-primary/40 bg-primary/10 text-primary"
                      : "border-input bg-background/60",
                  )}
                >
                  <span className="min-w-0">
                    <span className="block truncate font-mono">{model.id}</span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {model.owned_by || t("connection.model_picker_unknown_owner")}
                    </span>
                  </span>
                  {selected && <Check className="h-4 w-4 shrink-0" />}
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
    <Badge variant={ok ? "success" : "outline"}>
      {ok ? "✓" : "✗"} {label}
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
      <span className="inline-flex items-center gap-1 text-[0.7rem] font-normal text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
        {t("connection.models_loading")}
      </span>
    );
  }
  if (error) {
    return (
      <span
        className="text-[0.7rem] font-normal text-amber-500"
        title={error}
      >
        {t("connection.models_error")}
      </span>
    );
  }
  if (count > 0) {
    return (
      <span className="inline-flex items-center gap-1 text-[0.7rem] font-normal text-muted-foreground">
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
