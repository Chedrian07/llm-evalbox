import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type PricingEstimate } from "@/lib/api";
import { useApp } from "@/lib/store";
import { fmtCost, fmtNum } from "@/lib/format";

export function CostPreview() {
  const { t } = useTranslation();
  const { model, selectedBenches, samples, concurrency, thinking } = useApp();
  const [est, setEst] = useState<PricingEstimate | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (selectedBenches.size === 0 || !model) {
      setEst(null);
      return;
    }
    api
      .estimateCost(model, [...selectedBenches], samples, concurrency, thinking)
      .then((r) => {
        if (!cancelled) setEst(r);
      })
      .catch(() => {
        if (!cancelled) setEst(null);
      });
    return () => {
      cancelled = true;
    };
  }, [model, selectedBenches, samples, concurrency, thinking]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("cost.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        {est == null ? (
          <p className="text-sm text-muted-foreground">—</p>
        ) : (
          <div className="space-y-1 text-sm">
            <div className="text-2xl font-semibold tabular-nums">
              {est.est_cost_usd == null ? t("cost.unknown") : fmtCost(est.est_cost_usd)}
            </div>
            <div className="text-xs text-muted-foreground">
              {t("cost.tokens", {
                tokens: fmtNum(
                  est.est_prompt_tokens + est.est_completion_tokens + est.est_reasoning_tokens,
                ),
              })}{" "}
              · {t("cost.seconds", { seconds: fmtNum(est.est_seconds) })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
