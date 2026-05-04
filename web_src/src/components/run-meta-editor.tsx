import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Star, X } from "lucide-react";

import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";

/**
 * Inline editor for run-level metadata (starred / tags / notes). Designed
 * to live in the Results page header and the run-history sidebar's detail
 * pane. Persists via PATCH /api/history/{run_id} on every change so users
 * never need a "save" button.
 *
 * `runId` is required — there's no point editing meta for a run that
 * hasn't been persisted to history yet (a run that just finished but
 * failed to save would have `runId` but `null` initial values; PATCH 404s
 * are surfaced via `error`).
 */
export function RunMetaEditor({
  runId,
  initialTags = [],
  initialNotes = "",
  initialStarred = false,
  compact = false,
}: {
  runId: string;
  initialTags?: string[];
  initialNotes?: string | null;
  initialStarred?: boolean;
  compact?: boolean;
}) {
  const { t } = useTranslation();
  const [tags, setTags] = useState<string[]>(initialTags);
  const [notes, setNotes] = useState<string>(initialNotes ?? "");
  const [starred, setStarred] = useState<boolean>(initialStarred);
  const [tagInput, setTagInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  // When the parent swaps to a different run (history navigation), reset.
  useEffect(() => {
    setTags(initialTags);
    setNotes(initialNotes ?? "");
    setStarred(initialStarred);
    setError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  async function patch(payload: { tags?: string[]; notes?: string; starred?: boolean }) {
    setError(null);
    try {
      await api.patchHistory(runId, payload);
    } catch (e: any) {
      setError(e?.message?.slice(0, 200) || "patch failed");
    }
  }

  function toggleStar() {
    const next = !starred;
    setStarred(next);
    void patch({ starred: next });
  }

  function addTag(raw: string) {
    const cleaned = raw.replace(",", "").trim();
    if (!cleaned || tags.includes(cleaned)) {
      setTagInput("");
      return;
    }
    const next = [...tags, cleaned];
    setTags(next);
    setTagInput("");
    void patch({ tags: next });
  }

  function removeTag(name: string) {
    const next = tags.filter((t) => t !== name);
    setTags(next);
    void patch({ tags: next });
  }

  function handleNotesBlur() {
    if ((notes ?? "") === (initialNotes ?? "")) return;
    void patch({ notes });
  }

  return (
    <div className={cn("space-y-2", compact && "space-y-1")}>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={toggleStar}
          className={cn(
            "inline-flex h-7 items-center gap-1 rounded-md border px-2 text-xs transition",
            starred
              ? "border-amber-400/40 bg-amber-400/10 text-amber-300"
              : "border-border/50 text-muted-foreground hover:bg-accent/40",
          )}
          aria-pressed={starred}
          title={t("results.toggle_star", { defaultValue: "Star" })!}
        >
          <Star className={cn("h-3.5 w-3.5", starred && "fill-current")} />
          {starred ? t("results.starred", { defaultValue: "Starred" }) : t("results.star", { defaultValue: "Star" })}
        </button>
        <div className="flex flex-wrap items-center gap-1">
          {tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[0.65rem] text-primary"
            >
              {tag}
              <button
                type="button"
                onClick={() => removeTag(tag)}
                className="text-primary/70 transition hover:text-primary"
                aria-label={t("results.remove_tag", { defaultValue: "Remove tag" })!}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
          <Input
            value={tagInput}
            onChange={(e) => setTagInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === "," || e.key === "Tab") {
                e.preventDefault();
                addTag(tagInput);
              }
            }}
            onBlur={() => tagInput && addTag(tagInput)}
            placeholder={t("results.add_tag", { defaultValue: "+ tag" })!}
            className="h-6 w-24 px-2 text-xs"
            spellCheck={false}
          />
        </div>
      </div>
      {!compact && (
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={handleNotesBlur}
          placeholder={t("results.notes_placeholder", { defaultValue: "Notes…" })!}
          rows={2}
          className="w-full rounded-md border border-input bg-transparent px-2 py-1 text-xs"
        />
      )}
      {error && <p className="text-[0.65rem] text-destructive">{error}</p>}
    </div>
  );
}
