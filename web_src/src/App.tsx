import { useEffect } from "react";
import { useTranslation } from "react-i18next";

import { LocaleToggle } from "@/components/locale-toggle";
import { ResultsPage } from "@/pages/Results";
import { RunningPage } from "@/pages/Running";
import { SetupPage } from "@/pages/Setup";
import { api } from "@/lib/api";
import { useApp } from "@/lib/store";

export function App() {
  const { t } = useTranslation();
  const stage = useApp((s) => s.stage);
  const hydrated = useApp((s) => s.hydrated);
  const hydrateFromServer = useApp((s) => s.hydrateFromServer);

  // Pull defaults from /api/defaults once at mount so values surfaced by
  // `evalbox web` (with .env loaded) populate the connection / options
  // inputs instead of the OpenAI public defaults baked into the store.
  // Guarded by `hydrated` so React StrictMode / HMR re-runs don't clobber
  // user edits.
  useEffect(() => {
    if (hydrated) return;
    api.defaults().then(hydrateFromServer).catch(() => {
      // Backend down or older build — keep the static defaults.
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-muted/20">
      <header className="sticky top-0 z-20 border-b bg-background/95 backdrop-blur">
        <div className="container flex flex-col gap-3 py-3 md:flex-row md:items-center md:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <span className="text-base font-semibold tracking-tight">{t("app.title")}</span>
            <span className="hidden text-xs text-muted-foreground sm:inline">
              {t("app.subtitle")}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-1">
            <StageBadge stage="setup" current={stage} />
            <span className="text-muted-foreground/50">→</span>
            <StageBadge stage="running" current={stage} />
            <span className="text-muted-foreground/50">→</span>
            <StageBadge stage="results" current={stage} />
            <div className="ml-2">
              <LocaleToggle />
            </div>
          </div>
        </div>
      </header>
      <main className="container py-4 md:py-5">
        {stage === "setup" && <SetupPage />}
        {stage === "running" && <RunningPage />}
        {stage === "results" && <ResultsPage />}
      </main>
    </div>
  );
}

function StageBadge({ stage, current }: { stage: "setup" | "running" | "results"; current: string }) {
  const { t } = useTranslation();
  const active = stage === current;
  return (
    <span
      className={`rounded-md px-2 py-0.5 text-xs ${
        active ? "bg-primary text-primary-foreground" : "text-muted-foreground"
      }`}
    >
      {t(`stage.${stage}`)}
    </span>
  );
}
