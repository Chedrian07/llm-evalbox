import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { CheckCircle2, XCircle, Loader2, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";

export function ConnectionCard({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation();
  const s = useApp();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

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
  }, [s.hydrated, s.baseUrl, s.adapter, s.apiKeyEnv, compact]);

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
              onChange={(e) => s.setConnection({ adapter: e.target.value as any })}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            >
              <option value="auto">{t("connection.adapter_auto")}</option>
              <option value="chat_completions">{t("connection.adapter_chat")}</option>
              <option value="responses">{t("connection.adapter_responses")}</option>
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
