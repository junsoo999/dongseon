import { describe, expect, it } from 'vitest'
import { buildTodos, countdownLabel, tripCountdown } from './home'

describe('tripCountdown', () => {
  it('counts down, then counts trip days, then ends', () => {
    expect(countdownLabel(tripCountdown('2026-12-28', '2027-01-01', '2026-11-05'))).toBe('D-53')
    expect(countdownLabel(tripCountdown('2026-12-28', '2027-01-01', '2026-12-30'))).toBe('3일차')
    expect(tripCountdown('2026-12-28', '2027-01-01', '2027-01-03')).toEqual({
      kind: 'after',
      days: 2,
    })
  })
})

describe('buildTodos', () => {
  const base = {
    pins: 5,
    mustPins: 2,
    unresolvedPins: 0,
    bookedFlight: false,
    flightCandidates: 2,
    bookedStay: true,
    stayCandidates: 1,
    pendingSuggestions: 0,
    daysToStart: 53,
    googleWarnSkus: [],
  }
  it('asks for bookings and puts warnings first', () => {
    expect(buildTodos(base).map((t) => t.text)).toEqual(['항공권 확정하기 (후보 2개)'])
    const urgent = buildTodos({
      ...base,
      daysToStart: 10,
      unresolvedPins: 1,
      googleWarnSkus: ['places_details_pro'],
    })
    expect(
      urgent.every((t, i, a) => i === 0 || !(t.tone === 'warn' && a[i - 1].tone === 'info')),
    ).toBe(true)
    expect(urgent[0].tone).toBe('warn')
  })
  it('guides an empty trip', () => {
    expect(buildTodos({ ...base, pins: 0, mustPins: 0 })[0].text).toContain('가고 싶은 곳')
  })
})
