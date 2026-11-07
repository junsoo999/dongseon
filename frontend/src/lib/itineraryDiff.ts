import type { ItineraryOut } from '../api/client'

export type Change = {
  pinId: number
  label: string
  kind: 'added' | 'removed' | 'moved' | 'retimed'
  text: string
}

const md = (iso: string) => `${Number(iso.slice(5, 7))}/${Number(iso.slice(8, 10))}`

type Slot = { date: string; start: string; label: string }

function slots(it: ItineraryOut): Map<number, Slot> {
  const out = new Map<number, Slot>()
  for (const d of it.days)
    for (const i of d.items)
      if (i.pin_id !== null) out.set(i.pin_id, { date: d.date, start: i.start, label: i.label })
  return out
}

/** What changed from ``from`` to ``to``, grouped by date (the new date for moves). */
export function diffVersions(
  from: ItineraryOut,
  to: ItineraryOut,
): { date: string; changes: Change[] }[] {
  const a = slots(from)
  const b = slots(to)
  const byDate = new Map<string, Change[]>()
  const add = (date: string, c: Change) => byDate.set(date, [...(byDate.get(date) ?? []), c])
  for (const [pinId, s] of b) {
    const old = a.get(pinId)
    if (!old) add(s.date, { pinId, label: s.label, kind: 'added', text: `추가 (${s.start})` })
    else if (old.date !== s.date)
      add(s.date, {
        pinId,
        label: s.label,
        kind: 'moved',
        text: `${md(old.date)} → ${md(s.date)} 이동 (${s.start})`,
      })
    else if (old.start !== s.start)
      add(s.date, { pinId, label: s.label, kind: 'retimed', text: `${old.start} → ${s.start}` })
  }
  for (const [pinId, s] of a)
    if (!b.has(pinId)) add(s.date, { pinId, label: s.label, kind: 'removed', text: '빠짐' })
  return [...byDate.entries()]
    .sort(([x], [y]) => x.localeCompare(y))
    .map(([date, changes]) => ({ date, changes }))
}
