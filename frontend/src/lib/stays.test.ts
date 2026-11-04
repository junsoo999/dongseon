import { describe, expect, it } from 'vitest'
import { formatKrw } from './format'
import { parseAmount, rankColor } from './stays'

describe('stays helpers', () => {
  it('parses typed amounts', () => {
    expect(parseAmount('120,000')).toBe(120000)
    expect(parseAmount(' 5000 ')).toBe(5000)
    expect(parseAmount('')).toBeNull()
    expect(parseAmount('12.5')).toBeNull()
  })

  it('colors ranks from green to amber', () => {
    expect(rankColor(1, 7)).toBe('hsl(150 70% 38%)')
    expect(rankColor(7, 7)).toBe('hsl(40 70% 38%)')
    expect(rankColor(null, 7)).toBe('#6b7280')
  })

  it('formats won', () => {
    expect(formatKrw(253761.4)).toBe('₩253,761')
  })
})
