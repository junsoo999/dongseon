import { describe, expect, it } from 'vitest'
import { airlineLogoUrl, carrierCode, dayLabel, dayOffset } from './airlines'

describe('airlines', () => {
  it('reads carrier codes from flight numbers', () => {
    expect(carrierCode('KE703')).toBe('KE')
    expect(carrierCode('7C1108')).toBe('7C')
    expect(carrierCode('oz 101')).toBe('OZ')
    expect(carrierCode('')).toBeNull()
  })
  it('builds logo urls and day labels', () => {
    expect(airlineLogoUrl('7C', 64)).toBe(
      'https://img.wway.io/pics/root/7C@png?exar=1&rs=fit:64:64',
    )
    expect(dayLabel('2026-12-28T08:10')).toBe('12/28(월)')
    expect(dayOffset('2026-12-31T23:00', '2027-01-01T01:00')).toBe(1)
  })
})
