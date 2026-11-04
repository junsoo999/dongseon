/** Shade from green (best rank) to amber (worst); gray when unranked. */
export function rankColor(rank: number | null, total: number): string {
  if (rank === null || total <= 1) return '#6b7280'
  const t = (rank - 1) / (total - 1)
  return `hsl(${Math.round(150 - t * 110)} 70% 38%)`
}

export const CURRENCIES = ['JPY', 'KRW', 'USD'] as const

/** Parse a typed amount like "120,000" into an integer, or null when empty or invalid. */
export function parseAmount(text: string): number | null {
  const digits = text.replace(/[,\s]/g, '')
  if (!/^\d+$/.test(digits)) return null
  return Number(digits)
}
