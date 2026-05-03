import * as React from "react";
import { cn } from "@/lib/cn";

export const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("rounded-xl border bg-card text-card-foreground shadow-sm", className)}
      {...props}
    />
  ),
);
Card.displayName = "Card";

export const CardHeader = (p: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex flex-col gap-1.5 p-5 pb-2", p.className)} {...p} />
);
export const CardTitle = (p: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("text-base font-semibold leading-none", p.className)} {...p} />
);
export const CardDescription = (p: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("text-sm text-muted-foreground", p.className)} {...p} />
);
export const CardContent = (p: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("p-5 pt-2", p.className)} {...p} />
);
export const CardFooter = (p: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex items-center p-5 pt-0", p.className)} {...p} />
);
