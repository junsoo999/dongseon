import { describe, expect, it } from 'vitest'
import type { ItineraryOut } from '../api/client'
import { diffVersions } from './itineraryDiff'
import {
  addPin,
  draftOf,
  moveToDay,
  moveWithin,
  removePin,
  sameDraft,
  toEditIn,
  toggleLock,
} from './itineraryEdit'

function item(pinId: number, start: string, locked = false) {
  return {
    id: pinId * 10,
    pin_id: pinId,
    label: `장소${pinId}`,
    kind: 'visit',
    category: null,
    priority: 'want',
    google_place_id: null,
    lat: null,
    lng: null,
    start,
    end: start,
    move_min: null,
    move_mode: null,
    hours: null,
    hours_source: null,
    locked,
    warnings: [],
  }
}

function day(date: string, items: ReturnType<typeof item>[]) {
  return {
    date,
    start: '09:00',
    end: '21:00',
    depot: '숙소',
    back_at: null,
    back_move_min: null,
    warnings: [],
    items,
  }
}

function itin(days: ReturnType<typeof day>[], excluded: number[] = []): ItineraryOut {
  return {
    id: 1,
    version: 1,
    origin: 'solver',
    status: 'active',
    created_at: '2026-11-07T00:00:00Z',
    approx: true,
    days,
    dropped: excluded.map((p) => ({
      pin_id: p,
      label: `장소${p}`,
      priority: 'maybe',
      reason: '직접 뺐습니다',
      excluded: true,
    })),
  }
}

const base = itin(
  [day('2030-12-28', [item(1, '10:00'), item(2, '13:00', true)]), day('2030-12-29', [])],
  [3],
)

describe('draft editing', () => {
  it('reads layout, locks and removals from a version', () => {
    const d = draftOf(base)
    expect(d.days[0].pinIds).toEqual([1, 2])
    expect(d.locked).toEqual([2])
    expect(d.excluded).toEqual([3])
    expect(sameDraft(d, draftOf(base))).toBe(true)
  })

  it('locks what the user moves and keeps order changes', () => {
    let d = moveWithin(draftOf(base), 2, -1)
    expect(d.days[0].pinIds).toEqual([2, 1])
    d = moveToDay(d, 1, '2030-12-29')
    expect(d.days.map((x) => x.pinIds)).toEqual([[2], [1]])
    expect(d.locked.sort()).toEqual([1, 2])
    expect(moveWithin(d, 2, -1).days[0].pinIds).toEqual([2]) // already first
  })

  it('removes and adds back pins', () => {
    let d = removePin(draftOf(base), 2)
    expect(d.days[0].pinIds).toEqual([1])
    expect(d.locked).toEqual([])
    expect(d.excluded.sort()).toEqual([2, 3])
    d = addPin(d, 3, '2030-12-29')
    expect(d.days[1].pinIds).toEqual([3])
    expect(d.excluded).toEqual([2])
    expect(toggleLock(d, 3).locked).toEqual([])
    expect(toEditIn(d, true)).toEqual({
      days: [
        { date: '2030-12-28', pin_ids: [1] },
        { date: '2030-12-29', pin_ids: [3] },
      ],
      locked: [3],
      excluded: [2],
      resolve: true,
    })
  })
})

describe('diffVersions', () => {
  it('lists added, removed, moved and retimed visits by date', () => {
    const next = itin([
      day('2030-12-28', [item(2, '11:00')]),
      day('2030-12-29', [item(1, '10:00'), item(4, '15:00')]),
    ])
    const old = itin([day('2030-12-28', [item(1, '10:00'), item(2, '13:00'), item(5, '16:00')])])
    expect(diffVersions(old, next)).toEqual([
      {
        date: '2030-12-28',
        changes: [
          { pinId: 2, label: '장소2', kind: 'retimed', text: '13:00 → 11:00' },
          { pinId: 5, label: '장소5', kind: 'removed', text: '빠짐' },
        ],
      },
      {
        date: '2030-12-29',
        changes: [
          { pinId: 1, label: '장소1', kind: 'moved', text: '12/28 → 12/29 이동 (10:00)' },
          { pinId: 4, label: '장소4', kind: 'added', text: '추가 (15:00)' },
        ],
      },
    ])
  })
})
