import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  CheckCircle2,
  ChevronRight,
  Eraser,
  Info,
  Pause,
  Play,
  Terminal,
  XCircle,
} from "lucide-react";

import { cn } from "@/lib/cn";

/**
 * One line of the live log. The same envelope handles every kind of event we
 * receive over SSE; the renderer specialises by `kind`.
 *
 * - `system` (default): plain timestamp + message
 * - `progress`: dim gray, cleared on each subsequent same-bench progress so
 *   we don't flood the panel with N lines per second
 * - `item`: per-question result with prompt / response / reasoning preview
 * - `result`: bench completion summary
 * - `error`: red
 * - `done`: emerald
 */
export interface LogEntry {
  id: number;
  ts: number;
  kind: "system" | "progress" | "item" | "result" | "error" | "done";
  bench?: string;
  text: string;
  // Item-specific
  index?: number;
  total?: number;
  correct?: boolean;
  errorKind?: string;
  expected?: string;
  predicted?: string;
  promptPreview?: string;
  textPreview?: string;
  reasoningPreview?: string;
  latencyMs?: number;
  cacheHit?: boolean;
  tokens?: { prompt?: number; completion?: number; reasoning?: number };
}

const LIMITS = [200, 500, 1000, 2000] as const;

/**
 * Convert persisted run messages (backend `RunMessage[]`) into the same
 * LogEntry shape the live stream uses. Lets the Results page reuse this
 * panel for the saved Messages log without parallel rendering code.
 */
export function messagesToLogEntries(
  messages: { role?: string; content?: string; created_at?: string; metadata?: any }[],
): LogEntry[] {
  return messages.map((m, i) => {
    const md = m.metadata ?? {};
    const type = String(md.type ?? "system");
    const ts = m.created_at ? new Date(m.created_at).getTime() : Date.now();
    if (type === "item") {
      return {
        id: i,
        ts,
        kind: "item",
        bench: md.bench,
        index: md.index,
        total: md.total,
        correct: !!md.correct,
        errorKind: md.error_kind,
        expected: md.expected,
        predicted: md.predicted,
        promptPreview: md.prompt_preview,
        textPreview: md.text_preview,
        reasoningPreview: md.reasoning_preview,
        latencyMs: md.latency_ms,
        cacheHit: !!md.cache_hit,
        tokens: md.tokens,
        text: m.content ?? "",
      };
    }
    const kind: LogEntry["kind"] =
      type === "progress" || type === "result" || type === "error" || type === "done"
        ? type
        : "system";
    return {
      id: i,
      ts,
      kind,
      bench: md.bench,
      text: m.content ?? type,
    };
  });
}

export function LiveLogPanel({
  entries,
  onClear,
  defaultAutoScroll = true,
  defaultLimit = 500,
  defaultShowProgress = true,
}: {
  entries: LogEntry[];
  /** Optional. When omitted, the clear button is hidden — useful for static
      logs (Results page) that have no live-stream semantics. */
  onClear?: () => void;
  defaultAutoScroll?: boolean;
  defaultLimit?: (typeof LIMITS)[number];
  defaultShowProgress?: boolean;
}) {
  const { t } = useTranslation();
  const [autoScroll, setAutoScroll] = useState(defaultAutoScroll);
  const [limit, setLimit] = useState<(typeof LIMITS)[number]>(defaultLimit);
  const [showProgress, setShowProgress] = useState(defaultShowProgress);
  const scrollRef = useRef<HTMLDivElement>(null);

  const visible = useMemo(() => {
    const filtered = showProgress ? entries : entries.filter((e) => e.kind !== "progress");
    return filtered.slice(Math.max(0, filtered.length - limit));
  }, [entries, limit, showProgress]);

  // Auto-scroll to bottom when new entries arrive (if user hasn't disabled it
  // and we aren't already showing the bottom — the latter check avoids
  // hijacking the scroll position when the user is reading older lines).
  useEffect(() => {
    if (!autoScroll) return;
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [visible.length, autoScroll]);

  const lastUpdated = entries.length > 0 ? new Date(entries[entries.length - 1].ts) : null;

  return (
    <section className="flex h-full flex-col rounded-lg border border-border/60 surface-1">
      {/* Toolbar */}
      <header className="flex items-center justify-between border-b border-border/60 px-3 py-2">
        <div className="flex items-center gap-2 text-xs">
          <Terminal className="h-3.5 w-3.5 text-primary" />
          <span className="font-medium">{t("log.title", { defaultValue: "Live log" })}</span>
          <span className="text-muted-foreground">
            {t("log.count", {
              showing: visible.length,
              total: entries.length,
              defaultValue: "{{showing}} / {{total}} lines",
            })}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setShowProgress((v) => !v)}
            className={cn(
              "rounded-md border px-2 py-0.5 text-[0.65rem] transition",
              showProgress
                ? "border-border/40 text-muted-foreground hover:border-border"
                : "border-primary/40 bg-primary/10 text-primary",
            )}
            title={t("log.toggle_progress", { defaultValue: "Toggle progress lines" })!}
          >
            {showProgress ? "progress: on" : "progress: off"}
          </button>
          <select
            value={limit}
            onChange={(e) => setLimit(parseInt(e.target.value, 10) as any)}
            className="h-6 rounded-md border border-input bg-transparent px-1 text-[0.65rem]"
            aria-label={t("log.line_cap", { defaultValue: "Line cap" })!}
          >
            {LIMITS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setAutoScroll((v) => !v)}
            className={cn(
              "rounded-md border p-1 transition",
              autoScroll
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-border/40 text-muted-foreground hover:border-border",
            )}
            title={t("log.autoscroll", { defaultValue: "Auto-scroll" })!}
            aria-label={t("log.autoscroll", { defaultValue: "Auto-scroll" })!}
            aria-pressed={autoScroll}
          >
            {autoScroll ? <Play className="h-3 w-3" /> : <Pause className="h-3 w-3" />}
          </button>
          {onClear && (
            <button
              type="button"
              onClick={onClear}
              className="rounded-md border border-border/40 p-1 text-muted-foreground transition hover:border-border hover:text-foreground"
              title={t("log.clear", { defaultValue: "Clear" })!}
              aria-label={t("log.clear", { defaultValue: "Clear" })!}
            >
              <Eraser className="h-3 w-3" />
            </button>
          )}
        </div>
      </header>

      {/* Log body */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto bg-[hsl(222,30%,4%)] px-3 py-2 font-mono text-[0.72rem] leading-relaxed"
      >
        {visible.length === 0 ? (
          <p className="text-muted-foreground">
            {t("log.empty", { defaultValue: "Waiting for events…" })}
          </p>
        ) : (
          <ol className="space-y-0.5">
            {visible.map((e) => (
              <LogLine key={e.id} entry={e} />
            ))}
          </ol>
        )}
      </div>

      {/* Footer */}
      <footer className="flex items-center justify-between border-t border-border/60 px-3 py-1 text-[0.65rem] text-muted-foreground">
        <span>
          {t("log.last_updated", { defaultValue: "Last updated" })}:{" "}
          <span className="font-mono">
            {lastUpdated ? lastUpdated.toLocaleTimeString() : "—"}
          </span>
        </span>
        <span className={cn("h-1.5 w-1.5 rounded-full", autoScroll ? "bg-primary" : "bg-muted")} />
      </footer>
    </section>
  );
}

function LogLine({ entry }: { entry: LogEntry }) {
  const [expanded, setExpanded] = useState(entry.kind === "item" && !!entry.correct === false);
  const ts = formatTime(entry.ts);

  const colors = (() => {
    switch (entry.kind) {
      case "error":
        return { ts: "text-destructive/70", body: "text-destructive" };
      case "done":
        return { ts: "text-primary/60", body: "text-primary" };
      case "result":
        return { ts: "text-primary/60", body: "text-foreground" };
      case "item":
        return entry.correct
          ? { ts: "text-primary/60", body: "text-primary" }
          : { ts: "text-amber-500/70", body: "text-amber-300" };
      case "progress":
        return { ts: "text-muted-foreground/50", body: "text-muted-foreground" };
      default:
        return { ts: "text-muted-foreground", body: "text-foreground/80" };
    }
  })();

  if (entry.kind === "item") {
    const detail = [
      entry.errorKind && entry.errorKind !== "ok" && entry.errorKind !== "wrong_answer"
        ? `[${entry.errorKind}]`
        : null,
      entry.predicted ? `pred="${truncOneLine(entry.predicted, 30)}"` : null,
      entry.expected ? `exp="${truncOneLine(entry.expected, 30)}"` : null,
      entry.latencyMs != null ? `${(entry.latencyMs / 1000).toFixed(1)}s` : null,
      entry.cacheHit ? "cache" : null,
      entry.tokens?.completion != null
        ? `${entry.tokens.completion}↓${entry.tokens.reasoning ? `+${entry.tokens.reasoning}r` : ""}`
        : null,
    ]
      .filter(Boolean)
      .join(" · ");
    const hasPreview = !!(entry.promptPreview || entry.textPreview || entry.reasoningPreview);

    return (
      <li className={cn("group rounded px-1 transition hover:bg-white/[0.02]", colors.body)}>
        <div className="flex items-start gap-2">
          <span className={cn("shrink-0 select-none", colors.ts)}>{ts}</span>
          {hasPreview ? (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="shrink-0 text-muted-foreground/70 transition hover:text-foreground"
              title="toggle preview"
            >
              <ChevronRight
                className={cn("h-3 w-3 transition", expanded && "rotate-90")}
              />
            </button>
          ) : (
            <span className="w-3" />
          )}
          {entry.correct ? (
            <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-primary" />
          ) : (
            <XCircle className="mt-0.5 h-3 w-3 shrink-0 text-amber-400" />
          )}
          <span className="font-semibold">{entry.bench}</span>
          <span className="text-muted-foreground">
            #{entry.index}/{entry.total}
          </span>
          <span className="text-muted-foreground/80">{detail}</span>
        </div>
        {expanded && hasPreview && (
          <div className="ml-12 mt-1 space-y-1 border-l border-border/40 pl-3">
            {entry.promptPreview && (
              <PreviewBlock label="prompt" text={entry.promptPreview} tone="muted" />
            )}
            {entry.reasoningPreview && (
              <PreviewBlock label="reasoning" text={entry.reasoningPreview} tone="primary" />
            )}
            {entry.textPreview && (
              <PreviewBlock label="response" text={entry.textPreview} tone="foreground" />
            )}
          </div>
        )}
      </li>
    );
  }

  // All other kinds — single line.
  return (
    <li className={cn("flex items-start gap-2 rounded px-1 hover:bg-white/[0.02]", colors.body)}>
      <span className={cn("shrink-0 select-none", colors.ts)}>{ts}</span>
      <span className="w-3" />
      {entry.kind === "error" ? (
        <XCircle className="mt-0.5 h-3 w-3 shrink-0 text-destructive" />
      ) : entry.kind === "done" || entry.kind === "result" ? (
        <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-primary" />
      ) : (
        <Info className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground/60" />
      )}
      {entry.bench && <span className="font-semibold">{entry.bench}</span>}
      <span className="break-words">{entry.text}</span>
    </li>
  );
}

function PreviewBlock({
  label,
  text,
  tone,
}: {
  label: string;
  text: string;
  tone: "muted" | "primary" | "foreground";
}) {
  return (
    <div>
      <div className="text-[0.6rem] uppercase tracking-wide text-muted-foreground/70">{label}</div>
      <pre
        className={cn(
          "whitespace-pre-wrap break-words text-[0.7rem]",
          tone === "primary" && "text-primary/80",
          tone === "muted" && "text-muted-foreground",
          tone === "foreground" && "text-foreground",
        )}
      >
        {text}
      </pre>
    </div>
  );
}

function formatTime(ms: number): string {
  const d = new Date(ms);
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function truncOneLine(s: string, n: number): string {
  const flat = s.replace(/\s+/g, " ").trim();
  return flat.length <= n ? flat : flat.slice(0, n - 1) + "…";
}
