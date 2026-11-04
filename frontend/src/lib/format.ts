const NO_DECIMALS = new Set(['JPY', 'KRW'])

/** Format an integer amount in its own currency, e.g. (12000, "JPY") -> "JP¥12,000", (35000, 'KRW') -> "35,000원". */
export function formatMoney(amount: number, currency: string): string {
  if (!Number.isFinite(amount)) return '-'
  if (currency === 'KRW') return `${Math.round(amount).toLocaleString('ko-KR')}원`
  return new Intl.NumberFormat('ko-KR', {
    style: 'currency',
    currency,
    maximumFractionDigits: NO_DECIMALS.has(currency) ? 0 : 2,
  }).format(amount)
}

/** Minutes as Korean duration text, e.g. 95 -> "1시간 35분", 40 -> "40분". */
export function formatMinutes(min: number): string {
  if (!Number.isFinite(min)) return '-'
  const m = Math.round(min)
  const h = Math.floor(m / 60)
  const rest = m % 60
  if (h === 0) return `${rest}분`
  return rest === 0 ? `${h}시간` : `${h}시간 ${rest}분`
}

/** Days from `today` to `target` (both YYYY-MM-DD) as "D-3", "D-day", "D+2". */
export function dDay(target: string, today: string): string {
  const diff = Math.round((Date.parse(target) - Date.parse(today)) / 86_400_000)
  if (diff === 0) return 'D-day'
  return diff > 0 ? `D-${diff}` : `D+${-diff}`
}

/** Share of a free cap used, as "42%"; "-" when there is no cap. */
export function capShare(count: number, cap: number | null | undefined): string {
  if (!cap) return '-'
  return `${Math.floor((count / cap) * 100)}%`
}
