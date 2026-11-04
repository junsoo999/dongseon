/**
 * Airline logo by IATA code from the airline logo service Travelpayouts (Aviasales) publishes for travel apps.
 * Loaded by the browser on demand and never stored; components fall back to a code badge when it fails.
 */
export function airlineLogoUrl(code: string, px: number): string {
  return `https://img.wway.io/pics/root/${encodeURIComponent(code)}@png?exar=1&rs=fit:${px}:${px}`
}

/** IATA airline code from a flight number like "KE703" or "7C1108". */
export function carrierCode(flightNo: string | null | undefined): string | null {
  const m = /^([A-Z0-9]{2})\s?\d/.exec((flightNo ?? '').trim().toUpperCase())
  return m ? m[1] : null
}

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']

/** "2026-12-28T08:10" -> "12/28(월)". */
export function dayLabel(isoLocal: string): string {
  const [y, m, d] = isoLocal.slice(0, 10).split('-').map(Number)
  const wd = WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]
  return `${m}/${d}(${wd})`
}

/** Whole days between two local dates, e.g. +1 when a flight lands the next day. */
export function dayOffset(fromIso: string, toIso: string): number {
  const a = Date.parse(`${fromIso.slice(0, 10)}T00:00:00Z`)
  const b = Date.parse(`${toIso.slice(0, 10)}T00:00:00Z`)
  return Math.round((b - a) / 86_400_000)
}
