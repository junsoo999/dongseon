/** Where today sits relative to a trip (dates are YYYY-MM-DD in the trip's own calendar). */
export type Countdown =
  | { kind: 'before'; days: number }
  | { kind: 'during'; day: number; total: number }
  | { kind: 'after'; days: number }

function dayNumber(iso: string): number {
  return Math.round(Date.parse(`${iso}T00:00:00Z`) / 86_400_000)
}

export function tripCountdown(start: string, end: string, today: string): Countdown {
  const t = dayNumber(today)
  const s = dayNumber(start)
  const e = dayNumber(end)
  if (t < s) return { kind: 'before', days: s - t }
  if (t <= e) return { kind: 'during', day: t - s + 1, total: e - s + 1 }
  return { kind: 'after', days: t - e }
}

export function countdownLabel(c: Countdown): string {
  if (c.kind === 'before') return `D-${c.days}`
  if (c.kind === 'during') return `${c.day}일차`
  return '다녀옴'
}

export interface TodoInput {
  pins: number
  mustPins: number
  unresolvedPins: number
  bookedFlight: boolean
  flightCandidates: number
  bookedStay: boolean
  stayCandidates: number
  pendingSuggestions: number
  daysToStart: number | null
  googleWarnSkus: string[]
}

export interface Todo {
  tone: 'warn' | 'info'
  text: string
  to: string
}

/** What to do next, most urgent first. */
export function buildTodos(i: TodoInput): Todo[] {
  const out: Todo[] = []
  const soon = i.daysToStart !== null && i.daysToStart <= 30
  if (i.pins === 0)
    out.push({ tone: 'info', text: '가고 싶은 곳을 넣어 주세요 (AI 추천도 있어요)', to: '/places' })
  else if (i.mustPins === 0)
    out.push({ tone: 'info', text: "'꼭' 갈 곳을 정하면 숙소 동네 순위가 생겨요", to: '/places' })
  if (i.unresolvedPins > 0)
    out.push({ tone: 'warn', text: `지도에 연결 안 된 장소 ${i.unresolvedPins}곳`, to: '/places' })
  if (!i.bookedFlight)
    out.push({
      tone: soon ? 'warn' : 'info',
      text: i.flightCandidates
        ? `항공권 확정하기 (후보 ${i.flightCandidates}개)`
        : '항공권 후보를 골라 주세요',
      to: '/flights',
    })
  if (!i.bookedStay)
    out.push({
      tone: soon ? 'warn' : 'info',
      text: i.stayCandidates
        ? `숙소 확정하기 (후보 ${i.stayCandidates}곳)`
        : '숙소 후보를 골라 주세요',
      to: '/stays',
    })
  if (i.pendingSuggestions > 0)
    out.push({ tone: 'info', text: `AI 추천 ${i.pendingSuggestions}곳 검토하기`, to: '/places' })
  for (const sku of i.googleWarnSkus)
    out.push({ tone: 'warn', text: `Google 무료 한도에 가까움: ${sku}`, to: '/settings' })
  return out.sort((a, b) => (a.tone === b.tone ? 0 : a.tone === 'warn' ? -1 : 1))
}
