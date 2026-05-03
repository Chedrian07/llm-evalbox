// SPDX-License-Identifier: Apache-2.0
// Tiny IndexedDB helper for persisting completed run results in the browser.
// We don't pull in idb-keyval — a few raw IDBOpenDBRequest calls are enough.

const DB_NAME = "evalbox";
const DB_VERSION = 1;
const STORE = "runs";

export interface HistoryEntry {
  run_id: string;
  saved_at: number;
  model: string;
  base_url: string;
  result: any; // result.json payload
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
