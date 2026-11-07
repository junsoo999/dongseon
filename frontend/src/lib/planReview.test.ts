import { describe, expect, it } from 'vitest'
import { dayTitles } from './planReview'

const review = (source: string, titles: Array<[string, string]>) => ({
  id: 1,
  source,
  date: null,
  itinerary_version: 1,
  day_titles: titles.map(([date, title]) => ({ date, title })),
  notes: [],
  created_at: '2026-11-07T00:00:00Z',
})

describe('dayTitles', () => {
  it('prefers a rain plan title for its date', () => {
    const t = dayTitles({
      reviews: [
        review('rain', [['2030-12-29', '비 오는 날']]),
        review('review', [
          ['2030-12-28', '도착'],
          ['2030-12-29', '공원 산책'],
        ]),
      ],
      edits: [],
    })
    expect(t.get('2030-12-28')).toBe('도착')
    expect(t.get('2030-12-29')).toBe('비 오는 날')
    expect(dayTitles(undefined).size).toBe(0)
  })
})
