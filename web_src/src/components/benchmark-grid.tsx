import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { AlertTriangle, CheckSquare, Square } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, type BenchmarkInfo } from "@/lib/api";
import { useApp } from "@/lib/store";
import { cn } from "@/lib/cn";

const ORDER = ["knowledge", "reasoning", "math", "coding", "truthful", "multilingual", "safety", "other"];

export function BenchmarkGrid() {
  const { t } = useTranslation();
  const { selectedBenches, toggleBench } = useApp();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const q = useQuery({ queryKey: ["benchmarks"], queryFn: api.benchmarks });

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (q.data ?? []).filter((b) => {
      const catOk = category === "all" || b.category === category;
      const queryOk = !needle || b.name.toLowerCase().includes(needle);
      return catOk && queryOk;
    });
  }, [category, q.data, query]);

  if (q.isLoading) {
    return <p className="text-sm text-muted-foreground">…</p>;
  }
  if (q.isError) {
    return <p className="text-sm text-destructive">{(q.error as Error).message}</p>;
  }

  const groups = new Map<string, BenchmarkInfo[]>();
  for (const b of filtered) {
    if (!groups.has(b.category)) groups.set(b.category, []);
    groups.get(b.category)!.push(b);
  }
  const visibleSelected = filtered.filter((b) => selectedBenches.has(b.name)).length;
  const allVisibleSelected = filtered.length > 0 && visibleSelected === filtered.length;

  function selectVisible() {
    for (const b of filtered) {
      if (!selectedBenches.has(b.name)) toggleBench(b.name);
    }
  }

  function clearVisible() {
    for (const b of filtered) {
      if (selectedBenches.has(b.name)) toggleBench(b.name);
    }
  }

  return (
    <Card>
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>{t("benches.title")}</CardTitle>
          <div className="text-xs text-muted-foreground">
            {t("benches.selected_count", { count: selectedBenches.size })}
          </div>
        </div>
        <div className="grid gap-2 md:grid-cols-[1fr_auto_auto]">
          <Input
            value={query}
            placeholder={t("benches.search_placeholder")!}
            onChange={(e) => setQuery(e.target.value)}
          />
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
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
            onClick={allVisibleSelected ? clearVisible : selectVisible}
            disabled={filtered.length === 0}
          >
            {allVisibleSelected ? t("benches.clear_visible") : t("benches.select_visible")}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="grid gap-5">
        {filtered.length === 0 && (
          <p className="text-sm text-muted-foreground">{t("benches.no_matches")}</p>
        )}
        {ORDER.filter((k) => groups.has(k)).map((cat) => (
          <div key={cat}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {t(`benches.${cat}`)}
            </h3>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {groups.get(cat)!.map((b) => {
                const sel = selectedBenches.has(b.name);
                return (
                  <button
                    key={b.name}
                    onClick={() => toggleBench(b.name)}
                    className={cn(
                      "flex items-start gap-2 rounded-md border p-3 text-left transition-colors",
                      sel ? "border-primary bg-primary/5" : "border-input hover:bg-accent",
                    )}
                  >
                    {sel ? (
                      <CheckSquare className="mt-0.5 h-4 w-4 text-primary" />
                    ) : (
                      <Square className="mt-0.5 h-4 w-4 text-muted-foreground" />
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="font-medium">{b.name}</span>
                        {b.is_code_bench && (
                          <Badge variant="destructive">
                            <AlertTriangle className="h-3 w-3" /> code
                          </Badge>
                        )}
                        {b.license && (
                          <Badge variant="outline">{b.license}</Badge>
                        )}
                      </div>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        quick={b.quick_size}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
