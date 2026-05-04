// SPDX-License-Identifier: Apache-2.0
// Lightweight EventSource wrapper. The SSE event names match the backend:
// "status" | "progress" | "result" | "done" | "error" | "ping".

export type SSEEventType =
  | "status"
  | "progress"
  | "item"
  | "result"
  | "done"
  | "error"
  | "ping"
  | "message";

export interface SSEHandlers {
  onProgress?: (data: any) => void;
  onItem?: (data: any) => void;
  onResult?: (data: any) => void;
  onDone?: (data: any) => void;
  onError?: (data: any) => void;
  onAny?: (event: SSEEventType, data: any) => void;
}

export function subscribeRun(runId: string, handlers: SSEHandlers): () => void {
  const url = `/api/runs/${encodeURIComponent(runId)}/events`;
  const es = new EventSource(url);

  const dispatch = (event: MessageEvent, type: SSEEventType) => {
    let data: any = {};
    try {
      data = JSON.parse(event.data);
    } catch {
      data = { raw: event.data };
    }
    handlers.onAny?.(type, data);
    if (type === "progress") handlers.onProgress?.(data);
    else if (type === "item") handlers.onItem?.(data);
    else if (type === "result") handlers.onResult?.(data);
    else if (type === "done") {
      handlers.onDone?.(data);
      es.close();
    } else if (type === "error") {
      handlers.onError?.(data);
    }
  };

  for (const t of ["status", "progress", "item", "result", "done", "error", "ping"] as const) {
    es.addEventListener(t, (ev) => dispatch(ev as MessageEvent, t));
  }
  es.onerror = () => {
    handlers.onError?.({ message: "EventSource connection lost" });
    es.close();
  };

  return () => es.close();
}
