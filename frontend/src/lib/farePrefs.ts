import type { FarePrefsIO } from '../api/client'

export const STOPS_LABEL = (n: number | null | undefined) =>
  n === 0 ? '직항' : n === 1 ? '경유 1회까지' : n === 2 ? '경유 2회까지' : '경유 상관없음'

/** "6~12시 출발", "15시 이후 출발", or null when unrestricted. */
export function hoursLabel(
  from: number | null | undefined,
  to: number | null | undefined,
): string | null {
  const f = from ?? null
  const t = to ?? null
  if (f === null && t === null) return null
  if (f !== null && t !== null) return `${f}~${t}시 출발`
  return f !== null ? `${f}시 이후 출발` : `${t}시까지 출발`
}

/** Short chips describing the search, e.g. ["성인 2", "ICN → HND·NRT", "직항", "가는 편 6~12시 출발"]. */
export function prefsChips(p: FarePrefsIO): string[] {
  const people = p.children ? `성인 ${p.adults} · 어린이 ${p.children}` : `성인 ${p.adults}`
  const chips = [
    people,
    `${p.origins.join('·')} → ${p.destinations.join('·')}`,
    STOPS_LABEL(p.max_stops),
  ]
  const out = hoursLabel(p.out_dep_from, p.out_dep_to)
  const back = hoursLabel(p.back_dep_from, p.back_dep_to)
  if (out) chips.push(`가는 편 ${out}`)
  if (back) chips.push(`오는 편 ${back}`)
  if (p.checked_bags) chips.push(`위탁 ${p.checked_bags}개`)
  if (p.max_price_krw) chips.push(`₩${p.max_price_krw.toLocaleString('ko-KR')} 이하`)
  if (p.airlines_exclude?.length) chips.push(`제외 ${p.airlines_exclude.join(',')}`)
  return chips
}
