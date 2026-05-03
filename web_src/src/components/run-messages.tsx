import { AlertCircle, CheckCircle2, Clock3, MessageSquare, Terminal } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { RunMessage } from "@/lib/api";
import { cn } from "@/lib/cn";

export function RunMessages({
  messages,
  empty = "—",
  limit = 80,
}: {
  messages: RunMessage[];
  empty?: string;
  limit?: number;
}) {
  const visible = messages.slice(Math.max(0, messages.length - limit));

  if (visible.length === 0) {
    return <p className="text-sm text-muted-foreground">{empty}</p>;
  }

  return (
    <ol className="space-y-2">
      {visible.map((message, index) => {
        const kind = String(message.metadata?.type ?? message.role ?? "message");
        return (
          <li
            key={`${message.created_at ?? "no-time"}-${message.content}-${index}`}
            className={cn(
              "rounded-md border px-3 py-2 text-sm",
              kind === "error"
                ? "border-destructive/30 bg-destructive/5"
                : "border-input bg-background",
            )}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-2">
                <MessageIcon kind={kind} />
                <Badge variant={kind === "error" ? "destructive" : message.role === "assistant" ? "success" : "outline"}>
                  {message.role}
                </Badge>
                <span className="truncate font-mono text-xs text-muted-foreground">
                  {kind}
                </span>
              </div>
              {message.created_at && (
                <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock3 className="h-3 w-3" />
                  {formatTime(message.created_at)}
                </span>
              )}
            </div>
            <p className="mt-2 break-words leading-relaxed text-foreground">
              {message.content}
            </p>
          </li>
        );
      })}
    </ol>
  );
}

function MessageIcon({ kind }: { kind: string }) {
  if (kind === "error") return <AlertCircle className="h-4 w-4 text-destructive" />;
  if (kind === "result" || kind === "done") return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
  if (kind === "progress") return <Terminal className="h-4 w-4 text-primary" />;
  return <MessageSquare className="h-4 w-4 text-muted-foreground" />;
}

function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString();
}
