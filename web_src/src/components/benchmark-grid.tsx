import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { AlertTriangle, CheckSquare, Search, Square, X } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, type BenchmarkInfo } from "@/lib/api";
import { useApp } from "@/lib/store";
import { cn } from "@/lib/cn";

const ORDER = [
  "knowledge",
  "reasoning",
  "math",
  "coding",
  "truthful",
  "multilingual",
  "safety",
  "other",
] as const;

type Category = (typeof ORDER)[number];

export function BenchmarkGrid() {
  const { t } = useTranslation();
  const { selectedBenches, toggleBench } = useApp();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<Category | "all">("all");
  const q = useQuery({ queryKey: ["benchmarks"], queryFn: api.benchmarks });

  const all = q.data ?? [];

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return all.filter((b) => {
      const catOk = category === "all" || b.category === category;
      const queryOk = !needle || b.name.toLowerCase().includes(needle);
      return catOk && queryOk;
    });
  }, [category, all, query]);

  const groupCounts = useMemo(() => {
    const counts = new Map<string, { total: number; selected: number }>();
    for (const b of all) {
      const c = counts.get(b.category) ?? { total: 0, selected: 0 };
      c.total += 1;
      if (selectedBenches.has(b.name)) c.selected += 1;
      counts.set(b.category, c);
    }
    return counts;
  }, [all, selectedBenches]);

  const visibleSelected = filtered.filter((b) => selectedBenches.has(b.name)).length;
  const allVisibleSelected = filtered.length > 0 && visibleSelected === filtered.length;

  function selectVisible() {
    for (const b of filtered) if (!selectedBenches.has(b.name)) toggleBench(b.name);
  }
  function clearAllSelected() {
    for (const name of [...selectedBenches]) toggleBench(name);
  }

  if (q.isLoading) {
    return (
      <div className="rounded-lg border border-border/60 surface-1 p-6 text-sm text-muted-foreground">
        {t("benches.loading", { defaultValue: "Loading benchmarks…" })}
      </div>
    );
  }
  if (q.isError) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-sm text-destructive">
        {(q.error as Error).message}
      </div>
    );
  }

  return (
    <section className="rounded-lg border border-border/60 surface-1">
      <header className="flex flex-col gap-3 border-b border-border/60 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-baseline gap-2">
          <h2 className="text-base font-semibold">{t("benches.title")}</h2>
          {selectedBenches.size > 0 && (
            <button
              type="button"
              onClick={clearAllSelected}
              className="inline-flex items-center gap-1 rounded-full bg-primary/15 px-2 py-0.5 text-xs font-medium text-primary transition hover:bg-primary/25"
              title={t("benches.clear_all", { defaultValue: "Clear selection" })!}
            >
              {t("benches.selected_count", { count: selectedBenches.size })}
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
        <div className="flex w-full flex-wrap gap-2 sm:w-auto">
          <div className="relative min-w-[14rem] flex-1 sm:flex-initial">
            <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              placeholder={t("benches.search_placeholder")!}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-7"
            />
          </div>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as Category | "all")}
            className="flex h-9 rounded-md border border-input bg-transparent px-3 text-sm"
          >
            <option value="all">{t("benches.all_categories")}</option>
            {ORDER.map((cat) => (
              <option key={cat} value={cat}>
                {t(`benches.${cat}`)}
              </option>
            ))}
          </select>
          <Button
            variant="outline"
            size="sm"
            onClick={allVisibleSelected ? () => filtered.forEach((b) => toggleBench(b.name)) : selectVisible}
            disabled={filtered.length === 0}
            className="h-9"
          >
            {allVisibleSelected ? t("benches.clear_visible") : t("benches.select_visible")}
          </Button>
        </div>
      </header>

      <div className="p-4">
        {filtered.length === 0 ? (
          <p className="py-12 text-center text-sm text-muted-foreground">
            {t("benches.no_matches")}
          </p>
        ) : (
          <CategoryTabs
            counts={groupCounts}
            current={category}
            onChange={setCategory}
            t={t}
          />
        )}
        {filtered.length > 0 && (
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
            {filtered.map((b) => (
              <BenchCard
                key={b.name}
                b={b}
                selected={selectedBenches.has(b.name)}
                onToggle={() => toggleBench(b.name)}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function CategoryTabs({
  counts,
  current,
  onChange,
  t,
}: {
  counts: Map<string, { total: number; selected: number }>;
  current: Category | "all";
  onChange: (c: Category | "all") => void;
  t: (key: string, opts?: any) => string;
}) {
  const total = [...counts.values()].reduce((acc, v) => acc + v.total, 0);
  const sel = [...counts.values()].reduce((acc, v) => acc + v.selected, 0);
  return (
    <div className="-mx-1 flex flex-wrap gap-1 overflow-x-auto pb-1">
      <Tab
        active={current === "all"}
        onClick={() => onChange("all")}
        label={t("benches.all_categories")}
        count={total}
        selected={sel}
      />
      {ORDER.filter((c) => counts.has(c)).map((c) => {
        const v = counts.get(c)!;
        return (
          <Tab
            key={c}
            active={current === c}
            onClick={() => onChange(c)}
            label={t(`benches.${c}`)}
            count={v.total}
            selected={v.selected}
          />
        );
      })}
    </div>
  );
}

function Tab({
  active,
  onClick,
  label,
  count,
  selected,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count: number;
  selected: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors",
        active
          ? "border-primary/50 bg-primary/10 text-foreground"
          : "border-border/70 text-muted-foreground hover:bg-accent hover:text-foreground",
      )}
    >
      <span>{label}</span>
      <span className={cn("rounded-full px-1 text-[0.65rem]", selected > 0 ? "bg-primary/30 text-primary-foreground/95" : "bg-muted text-muted-foreground")}>
        {selected > 0 ? `${selected}/${count}` : count}
      </span>
    </button>
  );
}

function BenchCard({
  b,
  selected,
  onToggle,
}: {
  b: BenchmarkInfo;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      onClick={onToggle}
      aria-pressed={selected}
      className={cn(
        "group relative flex items-start gap-2 rounded-lg border p-3 text-left transition-all",
        selected
          ? "border-primary/60 bg-primary/[0.07] ring-1 ring-primary/40"
          : "border-border/60 surface-2 hover:border-border hover:bg-accent/40",
      )}
    >
      {selected ? (
        <CheckSquare className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
      ) : (
        <Square className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground/70" />
      )}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="font-medium leading-none">{b.name}</span>
          {b.is_code_bench && (
            <Badge
              variant="outline"
              className="border-amber-500/40 bg-amber-500/10 text-amber-300"
            >
              <AlertTriangle className="h-3 w-3" /> code
            </Badge>
          )}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[0.7rem] text-muted-foreground">
          {b.license && <span>{b.license}</span>}
          {b.license && <span className="text-muted-foreground/50">·</span>}
          <span className="font-mono">quick={b.quick_size}</span>
        </div>
      </div>
    </button>
  );
}
