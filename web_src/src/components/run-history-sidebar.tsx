import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  clearMergedHistory,
  deleteMergedHistory,
  listMergedHistory,
  type HistoryEntry,
} from "@/lib/history";
import { fmtAcc } from "@/lib/format";

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
  }, [refreshKey]);

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
        <CardTitle className="text-sm">{t("history.title")} ({entries.length})</CardTitle>
        {entries.length > 0 && (
          <Button size="sm" variant="ghost" onClick={nuke}>
            {t("history.clear")}
            <Trash2 className="h-3 w-3" />
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-2 p-3">
        {entries.length === 0 ? (
          <p className="text-xs text-muted-foreground">—</p>
        ) : (
          entries.map((e) => {
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
                className="w-full rounded-md border border-input p-2 text-left text-xs transition hover:bg-accent"
              >
                <div className="flex items-center justify-between gap-1">
                  <span className="font-medium truncate" title={e.run_id}>
                    {e.model}
                  </span>
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
