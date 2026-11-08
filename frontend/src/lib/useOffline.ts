import { useEffect, useState } from 'react'
import { useOfflineBundle } from '../api/hooks'
import { isUnreachable } from './offline'
import { useCurrentTrip } from './trip'

function useOnline(): boolean {
  const [online, setOnline] = useState(() =>
    typeof navigator === 'undefined' ? true : navigator.onLine,
  )
  useEffect(() => {
    const up = () => setOnline(true)
    const down = () => setOnline(false)
    window.addEventListener('online', up)
    window.addEventListener('offline', down)
    return () => {
      window.removeEventListener('online', up)
      window.removeEventListener('offline', down)
    }
  }, [])
  return online
}

/** Connection state plus the phone's offline copy of the current trip (refreshed while online). */
export function useOffline() {
  const { trip, trips } = useCurrentTrip()
  const online = useOnline()
  const tripsDown = trips.isError && isUnreachable(trips.error)
  const q = useOfflineBundle(trip?.id ?? null, tripsDown)
  return {
    online,
    /** The trip list could not be fetched: pages should read the offline copy. */
    tripsDown,
    bundle: q.data?.bundle ?? null,
    live: q.data?.live ?? false,
  }
}
