import * as React from "react";
import { cn } from "@/lib/cn";

type Variant = "default" | "outline" | "secondary" | "destructive" | "success";

const map: Record<Variant, string> = {
  default: "bg-primary/10 text-primary border-primary/30",
  outline: "border-input text-foreground",
  secondary: "bg-secondary text-secondary-foreground border-transparent",
  destructive: "bg-destructive/10 text-destructive border-destructive/30",
  success: "bg-emerald-500/10 text-emerald-500 border-emerald-500/30",
};

export const Badge = ({
  className,
  variant = "default",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: Variant }) => (
  <span
    className={cn(
      "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium",
      map[variant],
      className,
    )}
    {...props}
  />
);
