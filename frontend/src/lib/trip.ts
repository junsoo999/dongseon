import { useCallback, useState } from 'react'
import type { TripOut } from '../api/client'
import { useTrips } from '../api/hooks'

const KEY = 'dongseon.tripId'

function readStored(): number | null {
  try {
    const v = window.localStorage.getItem(KEY)
    return v ? Number(v) : null
  } catch {
    return null
  }
}

/**
 * Pick the default trip: the one ending soonest among those not over yet, else the latest one.
 * `today` is YYYY-MM-DD.
 */
export function defaultTrip(trips: TripOut[], today: string): TripOut | null {
  const upcoming = trips
    .filter((t) => t.end_date >= today)
    .sort((a, b) => a.start_date.localeCompare(b.start_date))
  if (upcoming.length > 0) return upcoming[0]
  return [...trips].sort((a, b) => b.start_date.localeCompare(a.start_date))[0] ?? null
}

export function todayIso(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** The trip being worked on: the remembered choice (this browser only), else the default. */
export function useCurrentTrip() {
  const trips = useTrips()
  const [storedId, setStoredId] = useState<number | null>(readStored)
  const list = trips.data ?? []
  const trip = list.find((t) => t.id === storedId) ?? defaultTrip(list, todayIso())

  const setTripId = useCallback((id: number) => {
    setStoredId(id)
    try {
      window.localStorage.setItem(KEY, String(id))
    } catch {
      // storage unavailable: the choice lasts until reload
    }
  }, [])

  return { trips, trip, setTripId }
}
