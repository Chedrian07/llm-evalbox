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
          <div className="col-span-2 space-y-1">
            <Label className="flex items-center justify-between">
              <span>{t("options.max_cost_usd")}</span>
              <span className="font-mono text-xs text-muted-foreground">
                {s.maxCostUsd == null ? "∞" : `$${s.maxCostUsd.toFixed(2)}`}
              </span>
            </Label>
            <input
              type="range"
              min={0}
              max={50}
              step={0.5}
              value={s.maxCostUsd ?? 0}
              onChange={(e) => {
                const v = parseFloat(e.target.value);
                s.setMaxCostUsd(v === 0 ? null : v);
              }}
              className="w-full accent-primary"
            />
            <div className="flex justify-between text-[0.65rem] text-muted-foreground">
              <span>$0 (no cap)</span><span>$25</span><span>$50</span>
            </div>
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
