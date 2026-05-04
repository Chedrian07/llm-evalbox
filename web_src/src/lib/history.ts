// SPDX-License-Identifier: Apache-2.0
// Tiny IndexedDB helper for persisting completed run results in the browser.
// We don't pull in idb-keyval — a few raw IDBOpenDBRequest calls are enough.

import { api, type RunResult } from "./api";

const DB_NAME = "evalbox";
const DB_VERSION = 1;
const STORE = "runs";

export interface HistoryEntry {
  run_id: string;
  saved_at: number;
  model: string;
  base_url: string;
  source?: "server" | "local";
  result: RunResult;
  tags?: string[];
  notes?: string | null;
  starred?: boolean;
}

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: "run_id" });
        store.createIndex("saved_at", "saved_at", { unique: false });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function saveHistory(entry: HistoryEntry): Promise<void> {
  const db = await open();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.objectStore(STORE).put(entry);
  });
  db.close();
}

export async function listHistory(): Promise<HistoryEntry[]> {
  const db = await open();
  const out = await new Promise<HistoryEntry[]>((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const req = tx.objectStore(STORE).getAll();
    req.onsuccess = () => resolve(req.result as HistoryEntry[]);
    req.onerror = () => reject(req.error);
  });
  db.close();
  // Newest first.
  return out.sort((a, b) => b.saved_at - a.saved_at);
}

export async function deleteHistory(run_id: string): Promise<void> {
  const db = await open();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.objectStore(STORE).delete(run_id);
  });
  db.close();
}

export async function clearHistory(): Promise<void> {
  const db = await open();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.objectStore(STORE).clear();
  });
  db.close();
}

export async function listServerHistory(limit = 100): Promise<HistoryEntry[]> {
  const rows = await api.history({ limit });
  const details = await Promise.allSettled(rows.map((row) => api.getHistory(row.run_id)));
  return details.flatMap((res, index) => {
    if (res.status !== "fulfilled") return [];
    const result = res.value;
    const row = rows[index];
    return [{
      run_id: result.run_id,
      saved_at: Date.parse(result.finished_at || result.started_at || row.started_at) || Date.now(),
      model: result.provider?.model || row.model || "?",
      base_url: result.provider?.base_url || row.base_url || "",
      source: "server" as const,
      result,
      tags: row.tags ?? [],
      notes: row.notes ?? null,
      starred: row.starred ?? false,
    }];
  });
}

export async function listMergedHistory(limit = 100): Promise<HistoryEntry[]> {
  const [server, local] = await Promise.all([
    listServerHistory(limit).catch(() => []),
    listHistory().catch(() => []),
  ]);
  const byId = new Map<string, HistoryEntry>();
  for (const entry of local) {
    byId.set(entry.run_id, { ...entry, source: entry.source ?? "local" });
  }
  for (const entry of server) {
    byId.set(entry.run_id, entry);
  }
  return Array.from(byId.values())
    .sort((a, b) => b.saved_at - a.saved_at)
    .slice(0, limit);
}

export async function deleteMergedHistory(run_id: string): Promise<void> {
  await Promise.allSettled([
    api.deleteHistory(run_id),
    deleteHistory(run_id),
  ]);
}

export async function clearMergedHistory(): Promise<void> {
  await Promise.allSettled([
    api.clearHistory(),
    clearHistory(),
  ]);
}
