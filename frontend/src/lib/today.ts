import type { ItemOut } from '../api/client'

/** "HH:MM" now in a timezone (the trip's, not the phone's). */
export function clockIn(timeZone: string, now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone,
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(now)
}

/** The stop under way at ``hhmm`` (if any) and the next one to start. Times are the plan's estimates. */
export function nowAndNext(
  items: ItemOut[],
  hhmm: string,
): { current: ItemOut | null; next: ItemOut | null; done: boolean } {
  const current = items.find((i) => i.start <= hhmm && hhmm < i.end) ?? null
  const next = items.find((i) => i.start > hhmm) ?? null
  return { current, next, done: items.length > 0 && !current && !next }
}

/** "YYYY-MM-DD" today in a timezone. */
export function dateIn(timeZone: string, now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone }).format(now)
}

/** Whether the trip is under way today, by the trip's own calendar. */
export function tripInProgress(
  trip: { start_date: string; end_date: string; timezone: string },
  now: Date = new Date(),
): boolean {
  const d = dateIn(trip.timezone, now)
  return trip.start_date <= d && d <= trip.end_date
}
