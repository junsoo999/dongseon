import { afterEach, describe, expect, it } from 'vitest'
import { ApiError, type OfflineOut } from '../api/client'
import { _clearMemory, isUnreachable, loadBundle, saveBundle } from './offline'

const bundle = (id: number): OfflineOut => ({
  trip: {
    id,
    title: 't',
    timezone: 'Asia/Tokyo',
    start_date: '2030-12-28',
    end_date: '2030-12-29',
  },
  generated_at: '2030-12-27T00:00:00Z',
  itinerary_id: null,
  version: null,
  days: [],
  checklist: [],
  bookings: { flights: [], stays: [], reservations: [] },
})

describe('offline copy', () => {
  afterEach(() => _clearMemory())

  it('keeps each trip and the latest one', async () => {
    await saveBundle(bundle(1))
    await saveBundle(bundle(2))
    expect((await loadBundle(1))?.trip.id).toBe(1)
    expect((await loadBundle(null))?.trip.id).toBe(2)
    expect(await loadBundle(3)).toBeNull()
  })

  it('treats network failures and 5xx as unreachable, not 4xx', () => {
    expect(isUnreachable(new TypeError('Failed to fetch'))).toBe(true)
    expect(isUnreachable(new ApiError(502, 'bad gateway'))).toBe(true)
    expect(isUnreachable(new ApiError(404, 'missing'))).toBe(false)
  })
})
