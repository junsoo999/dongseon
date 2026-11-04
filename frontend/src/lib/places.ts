import type { PinOut } from '../api/client'

export const CATEGORY_LABELS: Record<string, string> = {
  food: '식당',
  cafe: '카페',
  bar: '바',
  sight: '명소',
  museum: '박물관·미술관',
  shopping: '쇼핑',
  experience: '체험',
  other: '기타',
}

export const PRIORITIES = ['must', 'want', 'maybe'] as const
export type Priority = (typeof PRIORITIES)[number]

export const PRIORITY_LABELS: Record<Priority, string> = {
  must: '꼭',
  want: '가고 싶음',
  maybe: '여유 되면',
}

/** Marker and badge colors per priority (Tailwind-independent hex for map markers). */
export const PRIORITY_COLORS: Record<Priority, string> = {
  must: '#dc2626',
  want: '#0f766e',
  maybe: '#9ca3af',
}

export const MEAL_LABELS: Record<string, string> = { lunch: '점심', dinner: '저녁' }

export function categoryLabel(key: string): string {
  return CATEGORY_LABELS[key] ?? key
}

export function isPriority(value: string): value is Priority {
  return (PRIORITIES as readonly string[]).includes(value)
}

export interface PinFilter {
  categories: string[]
  priorities: Priority[]
}

export const EMPTY_FILTER: PinFilter = { categories: [], priorities: [] }

/** Keep pins matching every non-empty filter group. */
export function filterPins(pins: PinOut[], filter: PinFilter): PinOut[] {
  return pins.filter(
    (p) =>
      (filter.categories.length === 0 || filter.categories.includes(p.category)) &&
      (filter.priorities.length === 0 || (filter.priorities as string[]).includes(p.priority)),
  )
}

/** Sort for the list: priority (must first), then label. */
export function sortPins(pins: PinOut[]): PinOut[] {
  const rank = (p: PinOut) => (isPriority(p.priority) ? PRIORITIES.indexOf(p.priority) : 9)
  return [...pins].sort((a, b) => rank(a) - rank(b) || a.label.localeCompare(b.label, 'ko'))
}

/** Pins still waiting for a Google place match. */
export function unresolvedPins(pins: PinOut[]): PinOut[] {
  return pins.filter((p) => p.resolve_status !== 'ok')
}

export function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
}

/** A fresh Places autocomplete session token. */
export function newSessionToken(): string {
  return crypto.randomUUID()
}

/** Google Maps URL that opens the place in the app (Maps URLs, no key needed). */
export function mapsPlaceUrl(pin: Pick<PinOut, 'label' | 'google_place_id'>): string | null {
  if (!pin.google_place_id) return null
  const q = new URLSearchParams({ api: '1', query: pin.label, query_place_id: pin.google_place_id })
  return `https://www.google.com/maps/search/?${q.toString()}`
}
