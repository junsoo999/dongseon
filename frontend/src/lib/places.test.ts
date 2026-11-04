import { describe, expect, it } from 'vitest'
import type { PinOut } from '../api/client'
import { categoryLabel, filterPins, mapsPlaceUrl, sortPins, toggle, unresolvedPins } from './places'
import { defaultTrip } from './trip'
import type { TripOut } from '../api/client'

function pin(over: Partial<PinOut>): PinOut {
  return {
    id: 1,
    place_id: 1,
    google_place_id: 'g',
    label: '가',
    category: 'food',
    user_note: null,
    tag: null,
    source: 'search',
    resolve_status: 'ok',
    priority: 'want',
    dwell_min: 60,
    meal: null,
    locked_date: null,
    note: null,
    added_by: 'user',
    lat: 35,
    lng: 139,
    ...over,
  }
}

describe('pins', () => {
  const pins = [
    pin({ id: 1, label: '나', priority: 'maybe', category: 'cafe' }),
    pin({ id: 2, label: '다', priority: 'must' }),
    pin({ id: 3, label: '가', priority: 'must', resolve_status: 'failed' }),
  ]

  it('sorts by priority then label', () => {
    expect(sortPins(pins).map((p) => p.id)).toEqual([3, 2, 1])
  })

  it('filters by category and priority', () => {
    expect(filterPins(pins, { categories: ['food'], priorities: [] }).map((p) => p.id)).toEqual([
      2, 3,
    ])
    expect(filterPins(pins, { categories: [], priorities: ['maybe'] }).map((p) => p.id)).toEqual([
      1,
    ])
    expect(filterPins(pins, { categories: [], priorities: [] })).toHaveLength(3)
  })

  it('lists unresolved pins', () => {
    expect(unresolvedPins(pins).map((p) => p.id)).toEqual([3])
  })

  it('labels categories and toggles values', () => {
    expect(categoryLabel('museum')).toBe('박물관·미술관')
    expect(categoryLabel('new')).toBe('new')
    expect(toggle(['a'], 'b')).toEqual(['a', 'b'])
    expect(toggle(['a', 'b'], 'a')).toEqual(['b'])
  })
})

describe('defaultTrip', () => {
  const trip = (id: number, start: string, end: string) =>
    ({ id, start_date: start, end_date: end }) as TripOut

  it('prefers the nearest trip that is not over', () => {
    const trips = [
      trip(1, '2026-01-01', '2026-01-05'),
      trip(2, '2027-03-01', '2027-03-04'),
      trip(3, '2026-12-28', '2027-01-01'),
    ]
    expect(defaultTrip(trips, '2026-11-04')?.id).toBe(3)
    expect(defaultTrip(trips, '2026-12-30')?.id).toBe(3)
  })

  it('falls back to the latest past trip', () => {
    expect(
      defaultTrip(
        [trip(1, '2026-01-01', '2026-01-05'), trip(2, '2026-03-01', '2026-03-04')],
        '2026-11-04',
      )?.id,
    ).toBe(2)
    expect(defaultTrip([], '2026-11-04')).toBeNull()
  })
})

describe('mapsPlaceUrl', () => {
  it('builds a Maps URLs search link with the place id', () => {
    expect(mapsPlaceUrl({ label: '시장 A', google_place_id: 'ChIJx' })).toBe(
      'https://www.google.com/maps/search/?api=1&query=%EC%8B%9C%EC%9E%A5+A&query_place_id=ChIJx',
    )
    expect(mapsPlaceUrl({ label: 'x', google_place_id: null })).toBeNull()
  })
})
