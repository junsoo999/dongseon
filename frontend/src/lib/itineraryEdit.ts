import type { EditIn, ItineraryOut } from '../api/client'

/** A layout being edited: pin ids per date in order, plus locks and removals. */
export type Draft = {
  days: { date: string; pinIds: number[] }[]
  locked: number[]
  excluded: number[]
}

export function draftOf(it: ItineraryOut): Draft {
  return {
    days: it.days.map((d) => ({
      date: d.date,
      pinIds: d.items.flatMap((i) => (i.pin_id === null ? [] : [i.pin_id])),
    })),
    locked: it.days.flatMap((d) =>
      d.items.flatMap((i) => (i.locked && i.pin_id !== null ? [i.pin_id] : [])),
    ),
    excluded: it.dropped.filter((x) => x.excluded).map((x) => x.pin_id),
  }
}

const withLock = (locked: number[], pinId: number) =>
  locked.includes(pinId) ? locked : [...locked, pinId]

/** Move a pin up (-1) or down (+1) within its day. A moved pin is locked so a re-solve keeps it. */
export function moveWithin(d: Draft, pinId: number, delta: -1 | 1): Draft {
  const days = d.days.map((day) => {
    const i = day.pinIds.indexOf(pinId)
    const j = i + delta
    if (i < 0 || j < 0 || j >= day.pinIds.length) return day
    const pinIds = [...day.pinIds]
    ;[pinIds[i], pinIds[j]] = [pinIds[j], pinIds[i]]
    return { ...day, pinIds }
  })
  return { ...d, days, locked: withLock(d.locked, pinId) }
}

/** Move a pin to the end of another day, locked there. */
export function moveToDay(d: Draft, pinId: number, date: string): Draft {
  const days = d.days.map((day) => {
    const rest = day.pinIds.filter((p) => p !== pinId)
    return day.date === date ? { ...day, pinIds: [...rest, pinId] } : { ...day, pinIds: rest }
  })
  return { ...d, days, locked: withLock(d.locked, pinId) }
}

export function toggleLock(d: Draft, pinId: number): Draft {
  return {
    ...d,
    locked: d.locked.includes(pinId) ? d.locked.filter((p) => p !== pinId) : [...d.locked, pinId],
  }
}

/** Take a pin out of the plan; a re-solve keeps it out until it is added back. */
export function removePin(d: Draft, pinId: number): Draft {
  return {
    days: d.days.map((day) => ({ ...day, pinIds: day.pinIds.filter((p) => p !== pinId) })),
    locked: d.locked.filter((p) => p !== pinId),
    excluded: d.excluded.includes(pinId) ? d.excluded : [...d.excluded, pinId],
  }
}

/** Add a left-out pin to the end of a day, locked there. */
export function addPin(d: Draft, pinId: number, date: string): Draft {
  return { ...moveToDay(d, pinId, date), excluded: d.excluded.filter((p) => p !== pinId) }
}

export function toEditIn(d: Draft, resolve = false): EditIn {
  return {
    days: d.days.map((day) => ({ date: day.date, pin_ids: day.pinIds })),
    locked: d.locked.filter((p) => d.days.some((day) => day.pinIds.includes(p))),
    excluded: d.excluded,
    resolve,
  }
}

export function sameDraft(a: Draft, b: Draft): boolean {
  const key = (d: Draft) => JSON.stringify([d.days, [...d.locked].sort(), [...d.excluded].sort()])
  return key(a) === key(b)
}
