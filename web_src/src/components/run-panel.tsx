import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  AlertTriangle,
  ChevronDown,
  Clock,
  Coins,
  Cpu,
  Layers,
  Loader2,
  Play,
  RefreshCw,
  Settings2,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, type PricingEstimate } from "@/lib/api";
import { useApp } from "@/lib/store";
import { cn } from "@/lib/cn";
import { fmtCost, fmtNum } from "@/lib/format";

const THINKING_OPTS: { v: "auto" | "on" | "off"; descKey: string }[] = [
  { v: "auto", descKey: "thinking.auto_desc" },
  { v: "on", descKey: "thinking.on_desc" },
  { v: "off", descKey: "thinking.off_desc" },
];

const REASONING_OPTS = ["", "none", "minimal", "low", "medium", "high", "xhigh"] as const;

export function RunPanel({
  onStart,
  busy,
  err,
}: {
  onStart: () => void;
  busy: boolean;
  err: string | null;
}) {
  const { t } = useTranslation();
  const s = useApp();

  const codeBenchSelected = [...s.selectedBenches].some((n) =>
    ["humaneval", "mbpp", "livecodebench"].includes(n),
  );
  const codeBlocked = codeBenchSelected && !s.acceptCodeExec;
  const noBenches = s.selectedBenches.size === 0;
  const blocked = noBenches || codeBlocked || !s.baseUrl.trim() || !s.model.trim();

  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [est, setEst] = useState<PricingEstimate | null>(null);
  const [estLoading, setEstLoading] = useState(false);

  // Refresh cost estimate whenever the inputs that materially affect it change.
  useEffect(() => {
    let cancelled = false;
    if (s.selectedBenches.size === 0 || !s.model) {
      setEst(null);
      return;
    }
    setEstLoading(true);
    api
      .estimateCost(s.model, [...s.selectedBenches], s.samples, s.concurrency, s.thinking)
      .then((r) => !cancelled && setEst(r))
      .catch(() => !cancelled && setEst(null))
      .finally(() => !cancelled && setEstLoading(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s.model, s.selectedBenches, s.samples, s.concurrency, s.thinking]);

  // Slider max tracks max_cost_usd from .env so a user with $9999 cap doesn't
  // see a clamped slider on the right edge. We always anchor at a sane minimum
  // so very small values still get a useful drag range.
  const sliderMax = useMemo(() => {
    const cap = s.maxCostUsd ?? 0;
    if (cap <= 5) return 50;
    if (cap <= 50) return 50;
    if (cap <= 100) return 100;
    return Math.ceil(cap * 1.2);
  }, [s.maxCostUsd]);

  const selectedList = [...s.selectedBenches];
  const sampleLabel = s.samples === 0 ? t("benches.full_set") : s.samples.toLocaleString();

  return (
    <aside className="space-y-3 xl:sticky xl:top-20 xl:self-start">
      {/* Hero card — cost + run button */}
      <section className="overflow-hidden rounded-lg border border-primary/20 bg-gradient-to-b from-primary/[0.06] to-transparent">
        <div className="px-4 pt-4">
          <div className="flex items-center justify-between text-[0.7rem] uppercase tracking-wide text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <Coins className="h-3 w-3" /> {t("cost.title")}
            </span>
            {estLoading && <Loader2 className="h-3 w-3 animate-spin" />}
          </div>
          <div className="mt-1 font-mono text-3xl font-semibold tabular-nums">
            {est == null
              ? "—"
              : est.est_cost_usd == null
                ? "?"
                : fmtCost(est.est_cost_usd)}
          </div>
          <div className="mt-0.5 text-xs text-muted-foreground">
            {est == null
              ? t("plan.default_flags")
              : (
                <>
                  ≈ {fmtNum(est.est_prompt_tokens + est.est_completion_tokens + est.est_reasoning_tokens)}{" "}
                  {t("cost.tokens", { tokens: "" }).replace("≈  ", "")} ·{" "}
                  {t("cost.seconds", { seconds: fmtNum(est.est_seconds) })}
                </>
              )}
          </div>
        </div>

        {/* Mini stat row */}
        <div className="mx-4 mt-3 grid grid-cols-3 divide-x divide-border/40 rounded-md border border-border/40 bg-background/40 text-center text-xs">
          <Stat icon={<Layers className="h-3 w-3" />} value={selectedList.length} label={t("plan.benchmarks")} />
          <Stat icon={<Cpu className="h-3 w-3" />} value={sampleLabel} label={t("plan.samples")} />
          <Stat icon={<Clock className="h-3 w-3" />} value={s.thinking} label={t("plan.thinking")} />
        </div>

        {/* Selected benches chips */}
        {selectedList.length > 0 && (
          <div className="mx-4 mt-3 flex flex-wrap gap-1">
            {selectedList.slice(0, 12).map((b) => (
              <span
                key={b}
                className="rounded-full bg-primary/10 px-2 py-0.5 text-[0.65rem] font-medium text-primary"
              >
                {b}
              </span>
            ))}
            {selectedList.length > 12 && (
              <span className="rounded-full bg-muted/60 px-2 py-0.5 text-[0.65rem] text-muted-foreground">
                +{selectedList.length - 12}
              </span>
            )}
          </div>
        )}

        {/* Big primary action */}
        <div className="p-4 pt-3">
          <Button
            size="lg"
            onClick={onStart}
            disabled={blocked || busy}
            className="h-11 w-full text-base shadow-[0_0_0_1px_hsl(var(--primary)/0.3),0_4px_24px_-6px_hsl(var(--primary)/0.5)]"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {busy ? t("run.starting") : t("run.start")}
          </Button>

          {/* Status messages */}
          <div className="mt-2 space-y-1 text-xs">
            {err && <p className="text-destructive">{err}</p>}
            {noBenches && (
              <p className="inline-flex items-center gap-1 text-muted-foreground">
                <AlertTriangle className="h-3 w-3" />
                {t("run.no_benches")}
              </p>
            )}
            {codeBlocked && (
              <p className="inline-flex items-center gap-1 text-amber-400">
                <AlertTriangle className="h-3 w-3" />
                {t("run.code_consent_required")}
              </p>
            )}
          </div>
        </div>
      </section>

      {/* Thinking — segmented control */}
      <section className="rounded-lg border border-border/60 surface-1 p-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[0.7rem] uppercase tracking-wide text-muted-foreground">
            {t("thinking.title")}
          </span>
          <span className="text-[0.65rem] text-muted-foreground">
            {t(`thinking.${s.thinking}_desc`)}
          </span>
        </div>
        <div role="tablist" className="flex w-full rounded-md border border-input bg-background/40 p-0.5">
          {THINKING_OPTS.map(({ v }) => (
            <button
              key={v}
              type="button"
              role="tab"
              aria-selected={s.thinking === v}
              data-active={s.thinking === v}
              onClick={() => s.setThinking(v)}
              className="segmented-item flex-1 py-1.5 text-xs"
            >
              {v}
            </button>
          ))}
        </div>
      </section>

      {/* Quick options — samples / concurrency / cost cap */}
      <section className="rounded-lg border border-border/60 surface-1 p-3">
        <div className="mb-2 flex items-center gap-2">
          <Settings2 className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-[0.7rem] uppercase tracking-wide text-muted-foreground">
            {t("options.title")}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Compact label={t("benches.samples")} hint={t("benches.samples_help")}>
            <Input
              type="number"
              min={0}
              value={s.samples}
              onChange={(e) =>
                s.setSamples(Math.max(0, parseInt(e.target.value || "0", 10)))
              }
              className="h-8 text-sm"
            />
          </Compact>
          <Compact label={t("options.concurrency")}>
            <Input
              type="number"
              min={1}
              value={s.concurrency}
              onChange={(e) =>
                s.setConcurrency(Math.max(1, parseInt(e.target.value || "1", 10)))
              }
              className="h-8 text-sm"
            />
          </Compact>
        </div>

        <div className="mt-3">
          <div className="flex items-center justify-between text-[0.7rem] uppercase tracking-wide text-muted-foreground">
            <span>{t("options.max_cost_usd")}</span>
            <span className="font-mono normal-case tracking-normal text-foreground">
              {s.maxCostUsd == null ? "∞" : `$${s.maxCostUsd.toFixed(2)}`}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={sliderMax}
            step={Math.max(0.5, Math.round(sliderMax / 100))}
            value={s.maxCostUsd ?? 0}
            onChange={(e) => {
              const v = parseFloat(e.target.value);
              s.setMaxCostUsd(v === 0 ? null : v);
            }}
            className="mt-1 w-full accent-primary"
          />
          <div className="flex justify-between text-[0.6rem] text-muted-foreground">
            <span>$0</span>
            <span>${(sliderMax / 2).toFixed(0)}</span>
            <span>${sliderMax.toFixed(0)}</span>
          </div>
        </div>

        {/* Toggles */}
        <div className="mt-3 grid gap-1.5 border-t border-border/40 pt-3">
          <ToggleRow
            checked={s.acceptCodeExec}
            onChange={s.setAcceptCodeExec}
            label={t("options.accept_code_exec")}
            warn={codeBenchSelected && !s.acceptCodeExec}
          />
          <ToggleRow
            checked={s.strictFailures}
            onChange={s.setStrictFailures}
            label={t("options.strict_failures")}
          />
          <ToggleRow
            checked={s.noCache}
            onChange={s.setNoCache}
            label={t("options.no_cache")}
          />
        </div>

        {/* Advanced — collapsible */}
        <button
          type="button"
          onClick={() => setAdvancedOpen((v) => !v)}
          className="mt-3 flex w-full items-center justify-between rounded-md border border-dashed border-border/50 px-2 py-1.5 text-xs text-muted-foreground transition hover:border-border hover:text-foreground"
        >
          <span className="inline-flex items-center gap-1">
            <RefreshCw className="h-3 w-3" />
            {t("options.advanced", { defaultValue: "Advanced" })}
          </span>
          <ChevronDown className={cn("h-3.5 w-3.5 transition", advancedOpen && "rotate-180")} />
        </button>

        {advancedOpen && (
          <div className="mt-3 grid gap-3">
            <ToggleRow
              checked={s.promptCacheAware}
              onChange={s.setPromptCacheAware}
              label={t("options.prompt_cache_aware")}
            />
            <ToggleRow
              checked={s.noThinkingRerun}
              onChange={s.setNoThinkingRerun}
              label={t("options.no_thinking_rerun")}
            />

            <div>
              <Label className="text-[0.7rem] uppercase tracking-wide text-muted-foreground">
                {t("options.reasoning_effort")}
              </Label>
              <select
                value={s.reasoningEffort ?? ""}
                onChange={(e) => s.setReasoningEffort(e.target.value || null)}
                className="mt-1 flex h-8 w-full rounded-md border border-input bg-background/50 px-2 text-sm"
              >
                {REASONING_OPTS.map((v) => (
                  <option key={v} value={v}>
                    {v === "" ? t("options.reasoning_default") : v}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <Label className="text-[0.7rem] uppercase tracking-wide text-muted-foreground">
                {t("options.drop_params")}
              </Label>
              <Input
                value={s.dropParams}
                placeholder="top_k,seed"
                onChange={(e) => s.setDropParams(e.target.value)}
                spellCheck={false}
                className="mt-1 h-8 text-sm"
              />
              <p className="mt-1 text-[0.65rem] text-muted-foreground">
                {t("options.drop_params_help")}
              </p>
            </div>

            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                s.setThinking("off");
                s.setNoThinkingRerun(true);
                s.setReasoningEffort("none");
              }}
              title={t("options.fast_none_preset_help")!}
              className="h-8 w-full justify-start text-xs"
            >
              <Zap className="h-3.5 w-3.5" />
              {t("options.fast_none_preset")}
            </Button>
          </div>
        )}
      </section>
    </aside>
  );
}

function Stat({
  icon,
  value,
  label,
}: {
  icon: React.ReactNode;
  value: React.ReactNode;
  label: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-0.5 px-2 py-2">
      <span className="inline-flex items-center gap-1 text-muted-foreground">
        {icon}
        <span className="text-[0.6rem] uppercase tracking-wide">{label}</span>
      </span>
      <span className="font-mono text-sm font-medium">{value}</span>
    </div>
  );
}

function Compact({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-0.5">
      <Label className="text-[0.65rem] uppercase tracking-wide text-muted-foreground">
        {label}
      </Label>
      {children}
      {hint && <p className="text-[0.6rem] text-muted-foreground">{hint}</p>}
    </div>
  );
}

function ToggleRow({
  checked,
  onChange,
  label,
  warn,
}: {
  checked: boolean;
  onChange: (b: boolean) => void;
  label: string;
  warn?: boolean;
}) {
  return (
    <label
      className={cn(
        "flex cursor-pointer items-start gap-2 rounded-md border border-transparent px-1.5 py-1.5 text-xs transition",
        warn && "border-amber-500/30 bg-amber-500/5",
        "hover:bg-accent/30",
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-3.5 w-3.5 cursor-pointer rounded border-input accent-primary"
      />
      <span className="flex-1 leading-tight">{label}</span>
    </label>
  );
}

