import { describe, expect, it } from 'vitest'
import type { ItemOut } from '../api/client'
import { clockIn, nowAndNext, tripInProgress } from './today'
import { weatherLine, weatherLook } from './weather'

const item = (id: number, start: string, end: string) => ({ id, start, end }) as ItemOut

describe('nowAndNext', () => {
  const items = [item(1, '10:00', '11:30'), item(2, '12:00', '13:00')]
  it('finds the current and next stop', () => {
    expect(nowAndNext(items, '10:15')).toMatchObject({ current: { id: 1 }, next: { id: 2 } })
    expect(nowAndNext(items, '11:45')).toMatchObject({ current: null, next: { id: 2 } })
    expect(nowAndNext(items, '09:00')).toMatchObject({ current: null, next: { id: 1 } })
  })
  it('says the day is done after the last stop', () => {
    expect(nowAndNext(items, '13:00')).toEqual({ current: null, next: null, done: true })
  })
})

describe('clockIn', () => {
  it('uses the trip timezone', () => {
    expect(clockIn('Asia/Tokyo', new Date('2030-12-28T00:30:00Z'))).toBe('09:30')
  })
})

describe('tripInProgress', () => {
  it('uses the trip calendar', () => {
    const trip = { start_date: '2030-12-28', end_date: '2031-01-01', timezone: 'Asia/Tokyo' }
    expect(tripInProgress(trip, new Date('2030-12-27T15:30:00Z'))).toBe(true) // 00:30 on 12/28 in Tokyo
    expect(tripInProgress(trip, new Date('2030-12-27T14:30:00Z'))).toBe(false)
  })
})

describe('weather', () => {
  it('labels codes and lines', () => {
    expect(weatherLook(61).text).toBe('비')
    const base = { date: '2030-12-28', fetched_at: '', years: null, precip_mm: 0, rainy: true }
    expect(
      weatherLine({ ...base, kind: 'forecast', code: 61, tmax: 11.4, tmin: 3.6, precip_prob: 80 }),
    ).toBe('🌧️ 비 · 4°/11° · 강수 80%')
    expect(
      weatherLine({ ...base, kind: 'climate', code: 1, tmax: 10, tmin: 2, precip_prob: 40 }),
    ).toBe('평년 2°/10° · 비 온 해 40%')
  })
})
