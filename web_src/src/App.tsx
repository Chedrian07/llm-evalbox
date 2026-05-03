import { useTranslation } from "react-i18next";

import { LocaleToggle } from "@/components/locale-toggle";
import { ResultsPage } from "@/pages/Results";
import { RunningPage } from "@/pages/Running";
import { SetupPage } from "@/pages/Setup";
import { useApp } from "@/lib/store";

export function App() {
  const { t } = useTranslation();
  const stage = useApp((s) => s.stage);

  return (
    <div className="min-h-screen">
      <header className="border-b">
        <div className="container flex items-center justify-between py-3">
          <div className="flex items-center gap-3">
            <span className="text-base font-semibold tracking-tight">{t("app.title")}</span>
            <span className="hidden text-xs text-muted-foreground sm:inline">
              {t("app.subtitle")}
            </span>
          </div>
          <div className="flex items-center gap-1">
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
      <main className="container py-5">
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
