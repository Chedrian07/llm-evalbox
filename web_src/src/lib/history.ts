// SPDX-License-Identifier: Apache-2.0
// IndexedDB now serves as an OFFLINE FALLBACK only — the server's
// `runs.sqlite` is the canonical history. saveHistory() writes to
// IndexedDB only when the server fetch fails (so users on a flaky link
// or in private mode still get something), and listMergedHistory()
// prefers server results, layering local entries on top only for runs
// the server doesn't know about (e.g. created on another machine).
//
// The schema and DB version stay the same so existing IndexedDB stores
// from earlier versions still open without an upgrade event.

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

/**
 * Write a run to IndexedDB only if the server doesn't already know about
 * it (or the GET round-trip fails — typically offline). We attempt an
 * `api.getHistory(run_id)` first; if the server responds 200, the run is
 * canonically stored server-side and we don't need a local copy. Any
 * non-200 (404, 5xx, network error) falls through to IndexedDB so users
 * never lose data because the network blipped.
 */
export async function saveHistory(entry: HistoryEntry): Promise<void> {
  let serverHasIt = false;
  try {
    const detail = await api.getHistory(entry.run_id);
    serverHasIt = !!detail?.run_id;
  } catch {
    serverHasIt = false;
  }
  if (serverHasIt) return;

  try {
    const db = await open();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
      tx.objectStore(STORE).put(entry);
    });
    db.close();
  } catch {
    // IndexedDB unavailable (private mode, quota) — degrade silently.
    // The user still has the run-dir result.json on disk if CLI; the
    // Web UI Results page just won't list it after refresh.
  }
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

/**
 * Server is the source of truth. IndexedDB layers on top only for
 * runs the server doesn't have (offline mode or runs created on a
 * different machine that pushed to local but never reached this
 * server). When the server responds we don't drop those local-only
 * entries — they're still the user's, and a server they happen to be
 * connected to right now isn't authoritative for runs they made
 * elsewhere.
 */
export async function listMergedHistory(limit = 100): Promise<HistoryEntry[]> {
  const [server, local] = await Promise.all([
    listServerHistory(limit).catch(() => [] as HistoryEntry[]),
    listHistory().catch(() => [] as HistoryEntry[]),
  ]);
  const byId = new Map<string, HistoryEntry>();
  // Server first — its rows carry tags / notes / starred from SQLite.
  for (const entry of server) {
    byId.set(entry.run_id, entry);
  }
  // Local entries fill the gaps but never overwrite a server row.
  for (const entry of local) {
    if (!byId.has(entry.run_id)) {
      byId.set(entry.run_id, { ...entry, source: entry.source ?? "local" });
    }
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
