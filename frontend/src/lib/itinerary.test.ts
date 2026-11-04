import { describe, expect, it } from 'vitest'
import { directionsUrl, moveLabel } from './itinerary'

describe('itinerary helpers', () => {
  it('builds transit directions with the place id', () => {
    expect(directionsUrl({ label: '도쿄 국립박물관', google_place_id: 'ChIJx' })).toBe(
      'https://www.google.com/maps/dir/?api=1&destination=%EB%8F%84%EC%BF%84+%EA%B5%AD%EB%A6%BD%EB%B0%95%EB%AC%BC%EA%B4%80&travelmode=transit&destination_place_id=ChIJx',
    )
  })
  it('labels moves', () => {
    expect(moveLabel(25, 'rail')).toBe('🚃 25분 (근사)')
    expect(moveLabel(8, 'walk')).toBe('🚶 8분')
    expect(moveLabel(0, 'walk')).toBeNull()
  })
})
