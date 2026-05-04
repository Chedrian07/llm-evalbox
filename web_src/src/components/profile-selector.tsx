import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { BookmarkPlus, ChevronDown, Loader2, Save, Trash2, Users } from "lucide-react";

import { Input } from "@/components/ui/input";
import { api, type ConnectionProfile } from "@/lib/api";
import { useApp } from "@/lib/store";
import { cn } from "@/lib/cn";

/**
 * Connection profile picker. Lives in the ConnectionCard header.
 *
 * Profiles let users save the (base_url + model + adapter + api_key_env
 * + sampling) bundle they're using and switch between them with one
 * click. The API key value itself is never stored — `api_key_env`
 * points at an environment variable the backend resolves.
 *
 * Two surfaces:
 * - dropdown of saved profiles → click loads + bumps last_used_at
 * - inline "Save as profile" form (name input + Save button)
 */
export function ProfileSelector() {
  const { t } = useTranslation();
  const s = useApp();
  const [open, setOpen] = useState(false);
  const [profiles, setProfiles] = useState<ConnectionProfile[]>([]);
  const [loading, setLoading] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  async function refresh() {
    setLoading(true);
    try {
      const list = await api.listProfiles();
      setProfiles(list);
    } catch (e: any) {
      setError(e?.message?.slice(0, 200) || "list failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (s.hydrated) void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s.hydrated]);

  // Close popover on outside click.
  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  async function applyProfile(p: ConnectionProfile) {
    setError(null);
    s.setConnection({
      baseUrl: p.base_url ?? "",
      model: p.model ?? "",
      adapter: (p.adapter as any) || "auto",
      apiKeyEnv: p.api_key_env ?? "OPENAI_API_KEY",
    });
    setOpen(false);
    try {
      await api.useProfile(p.name);
      void refresh();
    } catch {
      // Best-effort; not critical if the touch fails.
    }
  }

  async function save() {
    const name = saveName.trim();
    if (!name) return;
    setBusy(true);
    setError(null);
    try {
      await api.saveProfile({
        name,
        base_url: s.baseUrl,
        model: s.model,
        adapter: s.adapter,
        api_key_env: s.apiKeyEnv,
      });
      setSaveOpen(false);
      setSaveName("");
      await refresh();
    } catch (e: any) {
      setError(e?.message?.slice(0, 200) || "save failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove(name: string) {
    setError(null);
    try {
      await api.deleteProfile(name);
      await refresh();
    } catch (e: any) {
      setError(e?.message?.slice(0, 200) || "delete failed");
    }
  }

  return (
    <div ref={popoverRef} className="relative">
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className={cn(
            "inline-flex h-7 items-center gap-1 rounded-md border px-2 text-xs transition",
            open
              ? "border-primary/50 bg-primary/10 text-foreground"
              : "border-border/50 text-muted-foreground hover:bg-accent/40 hover:text-foreground",
          )}
          aria-haspopup="listbox"
          aria-expanded={open}
        >
          <Users className="h-3.5 w-3.5" />
          <span>
            {t("profile.title", { defaultValue: "Profile" })}
            {profiles.length > 0 && (
              <span className="ml-1 text-muted-foreground">({profiles.length})</span>
            )}
          </span>
          <ChevronDown className={cn("h-3 w-3 transition", open && "rotate-180")} />
        </button>
        <button
          type="button"
          onClick={() => setSaveOpen((v) => !v)}
          className={cn(
            "inline-flex h-7 items-center gap-1 rounded-md border px-2 text-xs transition",
            saveOpen
              ? "border-primary/50 bg-primary/10 text-foreground"
              : "border-border/50 text-muted-foreground hover:bg-accent/40 hover:text-foreground",
          )}
          title={t("profile.save", { defaultValue: "Save as profile…" })!}
        >
          <BookmarkPlus className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Dropdown — saved profiles */}
      {open && (
        <div className="absolute right-0 top-9 z-30 w-72 rounded-md border border-border/60 surface-2 p-2 shadow-lg">
          {loading ? (
            <div className="flex items-center justify-center py-4 text-xs text-muted-foreground">
              <Loader2 className="mr-2 h-3 w-3 animate-spin" />
              {t("profile.loading", { defaultValue: "Loading…" })}
            </div>
          ) : profiles.length === 0 ? (
            <p className="px-2 py-3 text-center text-xs text-muted-foreground">
              {t("profile.empty", { defaultValue: "No saved profiles yet." })}
            </p>
          ) : (
            <ul className="max-h-72 space-y-0.5 overflow-y-auto">
              {profiles.map((p) => (
                <li key={p.name} className="group relative flex items-stretch gap-1">
                  <button
                    type="button"
                    onClick={() => applyProfile(p)}
                    className="min-w-0 flex-1 rounded-md px-2 py-1.5 text-left transition hover:bg-accent/40"
                  >
                    <div className="truncate text-xs font-medium">{p.name}</div>
                    <div className="truncate text-[0.6rem] text-muted-foreground">
                      {p.model ?? "—"} · {hostOnly(p.base_url ?? "")}
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      void remove(p.name);
                    }}
                    className="rounded-md px-1 text-muted-foreground/60 transition hover:text-destructive"
                    title={t("profile.delete", { defaultValue: "Delete" })!}
                    aria-label={t("profile.delete", { defaultValue: "Delete" })!}
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </li>
              ))}
            </ul>
          )}
          {error && <p className="mt-1 px-2 text-[0.65rem] text-destructive">{error}</p>}
        </div>
      )}

      {/* Inline "save as" form */}
      {saveOpen && (
        <div className="absolute right-0 top-9 z-30 w-72 rounded-md border border-border/60 surface-2 p-2 shadow-lg">
          <p className="mb-1 px-1 text-[0.65rem] uppercase tracking-wide text-muted-foreground">
            {t("profile.save_title", { defaultValue: "Save current connection" })}
          </p>
          <div className="flex items-center gap-1">
            <Input
              value={saveName}
              onChange={(e) => setSaveName(e.target.value)}
              placeholder={t("profile.name_placeholder", { defaultValue: "profile name" })!}
              className="h-7 text-xs"
              spellCheck={false}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !busy) void save();
                if (e.key === "Escape") setSaveOpen(false);
              }}
              autoFocus
            />
            <button
              type="button"
              onClick={() => void save()}
              disabled={busy || !saveName.trim()}
              className="inline-flex h-7 items-center gap-1 rounded-md border border-primary/40 bg-primary/10 px-2 text-xs text-primary transition hover:bg-primary/20 disabled:opacity-50"
            >
              {busy ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Save className="h-3 w-3" />
              )}
            </button>
          </div>
          <p className="mt-1 px-1 text-[0.6rem] text-muted-foreground">
            {t("profile.save_help", {
              defaultValue:
                "Stores base_url, model, adapter, api_key_env. The key value itself is never persisted.",
            })}
          </p>
          {error && <p className="mt-1 px-1 text-[0.65rem] text-destructive">{error}</p>}
        </div>
      )}
    </div>
  );
}

function hostOnly(url: string): string {
  try {
    return new URL(url).host || url;
  } catch {
    return url;
  }
}
