import { describe, expect, it } from 'vitest'
import { hoursLabel, prefsChips } from './farePrefs'

describe('fare prefs labels', () => {
  it('labels hour ranges', () => {
    expect(hoursLabel(6, 12)).toBe('6~12시 출발')
    expect(hoursLabel(15, null)).toBe('15시 이후 출발')
    expect(hoursLabel(null, 10)).toBe('10시까지 출발')
    expect(hoursLabel(null, null)).toBeNull()
  })
  it('summarizes the search', () => {
    expect(
      prefsChips({
        adults: 2,
        children: 1,
        origins: ['ICN'],
        destinations: ['HND', 'NRT'],
        max_stops: 0,
        checked_bags: 2,
        out_dep_from: 6,
        out_dep_to: 12,
        back_dep_from: null,
        back_dep_to: null,
        max_price_krw: 900000,
        airlines_exclude: ['7C'],
      }),
    ).toEqual([
      '성인 2 · 어린이 1',
      'ICN → HND·NRT',
      '직항',
      '가는 편 6~12시 출발',
      '위탁 2개',
      '₩900,000 이하',
      '제외 7C',
    ])
  })
})
