import { useTranslation } from "react-i18next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useApp } from "@/lib/store";
import { cn } from "@/lib/cn";

export function ThinkingToggle() {
  const { t } = useTranslation();
  const { thinking, setThinking } = useApp();
  const opts: { v: "auto" | "on" | "off"; desc: string }[] = [
    { v: "auto", desc: t("thinking.auto_desc") },
    { v: "on", desc: t("thinking.on_desc") },
    { v: "off", desc: t("thinking.off_desc") },
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("thinking.title")}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        {opts.map((o) => (
          <button
            key={o.v}
            onClick={() => setThinking(o.v)}
            className={cn(
              "flex flex-col items-start gap-0.5 rounded-md border p-3 text-left transition-colors",
              thinking === o.v
                ? "border-primary bg-primary/5"
                : "border-input hover:bg-accent",
            )}
          >
            <span className="font-medium">{t(`thinking.${o.v}`)}</span>
            <span className="text-xs text-muted-foreground">{o.desc}</span>
          </button>
        ))}
      </CardContent>
    </Card>
  );
}
