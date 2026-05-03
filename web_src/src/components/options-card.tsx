import { useTranslation } from "react-i18next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useApp } from "@/lib/store";

export function OptionsCard() {
  const { t } = useTranslation();
  const s = useApp();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("options.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label>{t("benches.samples")}</Label>
            <Input
              type="number"
              min={0}
              value={s.samples}
              onChange={(e) => s.setSamples(Math.max(0, parseInt(e.target.value || "0", 10)))}
            />
            <p className="text-xs text-muted-foreground">{t("benches.samples_help")}</p>
          </div>
          <div className="space-y-1">
            <Label>{t("options.concurrency")}</Label>
            <Input
              type="number"
              min={1}
              value={s.concurrency}
              onChange={(e) => s.setConcurrency(Math.max(1, parseInt(e.target.value || "1", 10)))}
            />
          </div>
          <div className="space-y-1">
            <Label>{t("options.max_cost_usd")}</Label>
            <Input
              type="number"
              min={0}
              step={0.5}
              value={s.maxCostUsd ?? ""}
              onChange={(e) =>
                s.setMaxCostUsd(e.target.value === "" ? null : parseFloat(e.target.value))
              }
            />
          </div>
        </div>
        <div className="space-y-2 pt-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={s.acceptCodeExec}
              onChange={(e) => s.setAcceptCodeExec(e.target.checked)}
              className="h-4 w-4 rounded border-input"
            />
            <span>{t("options.accept_code_exec")}</span>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={s.strictFailures}
              onChange={(e) => s.setStrictFailures(e.target.checked)}
              className="h-4 w-4 rounded border-input"
            />
            <span>{t("options.strict_failures")}</span>
          </label>
        </div>
      </CardContent>
    </Card>
  );
}
