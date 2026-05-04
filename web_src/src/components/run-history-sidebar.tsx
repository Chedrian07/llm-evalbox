import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Search, Star, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  clearMergedHistory,
  deleteMergedHistory,
  listMergedHistory,
  type HistoryEntry,
} from "@/lib/history";
import { fmtAcc } from "@/lib/format";
import { cn } from "@/lib/cn";

interface Props {
  /** Triggered whenever the history list changes (after add/delete/clear). */
  onChange?: (entries: HistoryEntry[]) => void;
  onSelect?: (entry: HistoryEntry) => void;
  /** Bumped by the parent to force a re-read after a fresh save. */
  refreshKey?: number;
}

export function RunHistorySidebar({ onChange, onSelect, refreshKey }: Props) {
  const { t } = useTranslation();
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [query, setQuery] = useState("");
  const [starredOnly, setStarredOnly] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listMergedHistory()
      .then((rows) => {
        if (!cancelled) {
          setEntries(rows);
          onChange?.(rows);
        }
      })
      .catch(() => {
        // IndexedDB unavailable (private mode etc.) — degrade silently.
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  // Client-side filter over the merged set. Server `?starred=true` is also
  // available but the merged set includes IndexedDB-only entries, so we
  // filter here to keep behaviour consistent.
  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return entries.filter((e) => {
      if (starredOnly && !e.starred) return false;
      if (!q) return true;
      const haystack = `${e.model} ${(e.tags ?? []).join(" ")} ${e.notes ?? ""}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [entries, query, starredOnly]);

  async function remove(id: string) {
    await deleteMergedHistory(id);
    const rows = await listMergedHistory();
    setEntries(rows);
    onChange?.(rows);
  }

  async function nuke() {
    await clearMergedHistory();
    setEntries([]);
    onChange?.([]);
  }

  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-sm">
          {t("history.title")} ({visible.length}/{entries.length})
        </CardTitle>
        {entries.length > 0 && (
          <Button size="sm" variant="ghost" onClick={nuke}>
            {t("history.clear")}
            <Trash2 className="h-3 w-3" />
          </Button>
        )}
      </CardHeader>
      {entries.length > 0 && (
        <div className="px-3 pb-2">
          <div className="flex items-center gap-1.5">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                placeholder={
                  t("history.search_placeholder", { defaultValue: "model · tag · notes" })!
                }
                onChange={(e) => setQuery(e.target.value)}
                className="h-7 pl-6 text-xs"
              />
            </div>
            <button
              type="button"
              onClick={() => setStarredOnly((v) => !v)}
              className={cn(
                "inline-flex h-7 items-center gap-1 rounded-md border px-2 text-[0.65rem] transition",
                starredOnly
                  ? "border-amber-400/40 bg-amber-400/10 text-amber-300"
                  : "border-border/50 text-muted-foreground hover:bg-accent/40",
              )}
              aria-pressed={starredOnly}
              title={t("history.starred_only", { defaultValue: "Starred only" })!}
            >
              <Star className={cn("h-3 w-3", starredOnly && "fill-current")} />
            </button>
          </div>
        </div>
      )}
      <CardContent className="space-y-2 p-3 pt-0">
        {visible.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            {entries.length === 0 ? "—" : t("history.no_matches", { defaultValue: "no matches" })}
          </p>
        ) : (
          visible.map((e) => {
            const acc = e.result?.totals?.accuracy_macro;
            const cost = e.result?.totals?.cost_usd_estimated;
            return (
              <div
                key={e.run_id}
                role="button"
                tabIndex={0}
                onClick={() => onSelect?.(e)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") onSelect?.(e);
                }}
                className={cn(
                  "w-full rounded-md border p-2 text-left text-xs transition hover:bg-accent",
                  e.starred ? "border-amber-400/30 bg-amber-400/[0.04]" : "border-input",
                )}
              >
                <div className="flex items-center justify-between gap-1">
                  <div className="flex min-w-0 items-center gap-1">
                    {e.starred && (
                      <Star className="h-3 w-3 shrink-0 fill-current text-amber-400" />
                    )}
                    <span className="font-medium truncate" title={e.run_id}>
                      {e.model}
                    </span>
                  </div>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-5 w-5"
                    onClick={(event) => {
                      event.stopPropagation();
                      void remove(e.run_id);
                    }}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
                <div className="mt-1 flex items-center gap-2 text-muted-foreground">
                  <Badge variant="outline">acc {fmtAcc(acc)}</Badge>
                  <Badge variant="secondary">{e.source ?? "local"}</Badge>
                  <span>{cost == null ? "—" : `$${cost.toFixed(3)}`}</span>
                </div>
                {e.tags && e.tags.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-0.5">
                    {e.tags.slice(0, 4).map((tag) => (
                      <span
                        key={tag}
                        className="rounded-full bg-primary/10 px-1.5 py-0 text-[0.6rem] text-primary"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                <div className="mt-0.5 text-[0.7rem] text-muted-foreground/70 truncate">
                  {new Date(e.saved_at).toLocaleString()}
                </div>
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
