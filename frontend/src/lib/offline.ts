import { ApiError, type OfflineOut } from '../api/client'

/**
 * The phone's copy of the active plan, checklist and bookings (IndexedDB), for reading without a connection.
 * It holds app data only: no Google opening hours, travel times, coordinates or map tiles.
 */
const DB = 'dongseon'
const STORE = 'offline'
const LATEST = 'latest'

const memory = new Map<string, OfflineOut>() // when IndexedDB is unavailable (tests, private mode)

function open(): Promise<IDBDatabase | null> {
  if (typeof indexedDB === 'undefined') return Promise.resolve(null)
  return new Promise((resolve) => {
    try {
      const req = indexedDB.open(DB, 1)
      req.onupgradeneeded = () => req.result.createObjectStore(STORE)
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => resolve(null)
    } catch {
      resolve(null)
    }
  })
}

async function run<T>(
  mode: IDBTransactionMode,
  fn: (s: IDBObjectStore) => IDBRequest<T>,
): Promise<T | null> {
  const db = await open()
  if (!db) return null
  return new Promise((resolve) => {
    try {
      const req = fn(db.transaction(STORE, mode).objectStore(STORE))
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => resolve(null)
    } catch {
      resolve(null)
    }
  })
}

/** Keep the bundle under its trip id and as the latest one (opened when the trip list cannot load). */
export async function saveBundle(b: OfflineOut): Promise<void> {
  memory.set(String(b.trip.id), b)
  memory.set(LATEST, b)
  await run('readwrite', (s) => s.put(b, String(b.trip.id)))
  await run('readwrite', (s) => s.put(b, LATEST))
}

export async function loadBundle(tripId: number | null): Promise<OfflineOut | null> {
  const key = tripId === null ? LATEST : String(tripId)
  const stored = await run<OfflineOut | undefined>('readonly', (s) => s.get(key))
  return stored ?? memory.get(key) ?? null
}

/** The server cannot be reached: no network, or the home Mac or the edge is down (5xx). */
export function isUnreachable(err: unknown): boolean {
  if (err instanceof ApiError) return err.status >= 500
  return err instanceof TypeError // fetch rejects with TypeError when offline
}

/** "11/8 09:30" in the phone's own clock, for "saved at". */
export function savedAtLabel(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** Test hook: forget the in-memory copy. */
export function _clearMemory(): void {
  memory.clear()
}
