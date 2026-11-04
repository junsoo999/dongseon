import { describe, expect, it } from 'vitest'
import {
  capShare,
  dDay,
  formatLocal,
  formatMinutes,
  formatMoney,
  formatSpan,
  minutesBetween,
} from './format'

describe('formatMoney', () => {
  it('keeps JPY and KRW without decimals', () => {
    expect(formatMoney(12000, 'JPY')).toBe('JP¥12,000')
    expect(formatMoney(35000, 'KRW')).toBe('35,000원')
  })
  it('handles non-finite values', () => {
    expect(formatMoney(Number.NaN, 'JPY')).toBe('-')
  })
})

describe('formatMinutes', () => {
  it('formats hours and minutes', () => {
    expect(formatMinutes(40)).toBe('40분')
    expect(formatMinutes(60)).toBe('1시간')
    expect(formatMinutes(95)).toBe('1시간 35분')
  })
})

describe('dDay', () => {
  it('counts calendar days', () => {
    expect(dDay('2026-12-28', '2026-12-25')).toBe('D-3')
    expect(dDay('2026-12-28', '2026-12-28')).toBe('D-day')
    expect(dDay('2026-12-28', '2026-12-30')).toBe('D+2')
  })
})

describe('capShare', () => {
  it('returns a floor percentage or dash', () => {
    expect(capShare(4210, 10000)).toBe('42%')
    expect(capShare(5, null)).toBe('-')
  })
})

describe('long spans and local times', () => {
  it('formats days', () => {
    expect(formatSpan(4 * 1440 + 115)).toBe('4일 1시간 55분')
    expect(formatSpan(2 * 1440)).toBe('2일')
    expect(formatSpan(90)).toBe('1시간 30분')
  })
  it('formats local timestamps without timezone math', () => {
    expect(formatLocal('2030-12-28T09:05')).toBe('12/28 09:05')
    expect(minutesBetween('2030-12-28T09:00', '2030-12-29T10:30')).toBe(1530)
  })
})
