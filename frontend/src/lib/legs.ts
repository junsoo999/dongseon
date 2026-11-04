import { minutesBetween } from './format'

export interface LegSegment {
  flight: string | null
  carrierCode: string | null
  carrier: string | null
  depAirport: string
  depLocal: string
  arrAirport: string
  arrLocal: string
  durationMin: number
}

/** Total minutes of a direction: flights plus layovers (each layover sits at one airport, so local times compare). */
export function directionMinutes(segs: LegSegment[]): number {
  let total = 0
  segs.forEach((s, i) => {
    total += s.durationMin
    if (i > 0) total += Math.max(0, minutesBetween(segs[i - 1].arrLocal, s.depLocal))
  })
  return total
}
