import { useTranslation } from "react-i18next";
import { Languages } from "lucide-react";
import { Button } from "@/components/ui/button";

export function LocaleToggle() {
  const { i18n } = useTranslation();
  const next = i18n.language?.startsWith("ko") ? "en" : "ko";
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => void i18n.changeLanguage(next)}
      className="gap-1"
    >
      <Languages className="h-4 w-4" />
      <span className="uppercase">{next}</span>
    </Button>
  );
}
