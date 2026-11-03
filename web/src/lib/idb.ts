import type { CheckInput, SavedResult } from "../types";

const DB_NAME = "haske";
const DB_VERSION = 1;
const SAVED = "saved";
const QUEUE = "queue";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(SAVED)) {
        db.createObjectStore(SAVED, { keyPath: "id" });
      }
      if (!db.objectStoreNames.contains(QUEUE)) {
        db.createObjectStore(QUEUE, { keyPath: "id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function tx(db: IDBDatabase, store: string, mode: IDBTransactionMode = "readonly"): IDBObjectStore {
  return db.transaction(store, mode).objectStore(store);
}

function reqAsPromise<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function saveResult(entry: SavedResult): Promise<void> {
  const db = await openDb();
  await reqAsPromise(tx(db, SAVED, "readwrite").put(entry));
}

export async function listSaved(): Promise<SavedResult[]> {
  const db = await openDb();
  const all = await reqAsPromise(tx(db, SAVED).getAll() as IDBRequest<SavedResult[]>);
  return all.sort((a, b) => (a.savedAt < b.savedAt ? 1 : -1));
}

export async function getSaved(id: string): Promise<SavedResult | undefined> {
  const db = await openDb();
  return reqAsPromise(tx(db, SAVED).get(id) as IDBRequest<SavedResult | undefined>);
}

export async function deleteSaved(id: string): Promise<void> {
  const db = await openDb();
  await reqAsPromise(tx(db, SAVED, "readwrite").delete(id));
}

export async function clearSaved(): Promise<void> {
  const db = await openDb();
  await reqAsPromise(tx(db, SAVED, "readwrite").clear());
}

export interface QueuedCheck {
  id: string;
  input: CheckInput;
  createdAt: string;
}

export async function enqueueCheck(input: CheckInput): Promise<void> {
  const db = await openDb();
  const item: QueuedCheck = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    input,
    createdAt: new Date().toISOString(),
  };
  await reqAsPromise(tx(db, QUEUE, "readwrite").put(item));
}

export async function listQueue(): Promise<QueuedCheck[]> {
  const db = await openDb();
  const all = await reqAsPromise(tx(db, QUEUE).getAll() as IDBRequest<QueuedCheck[]>);
  return all.sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
}

export async function removeFromQueue(id: string): Promise<void> {
  const db = await openDb();
  await reqAsPromise(tx(db, QUEUE, "readwrite").delete(id));
}
