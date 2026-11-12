import type { TripOut } from '../api/client'
import { usePatchTrip } from '../api/hooks'

type Field = 'arrival_airport' | 'departure_airport'

/** The airports the first day starts at and the last day ends at, until a flight is booked. */
export function TripAirports({ trip }: { trip: TripOut }) {
  const patch = usePatchTrip(trip.id)
  const choices = trip.airport_choices ?? []
  if (choices.length === 0) return null
  const select = (field: Field, label: string) => (
    <label className="flex min-h-11 items-center gap-1.5">
      <span className="text-gray-600">{label}</span>
      <select
        value={trip[field] ?? ''}
        disabled={patch.isPending}
        onChange={(e) => patch.mutate({ [field]: e.target.value })}
        className="min-h-9 rounded-lg border border-gray-300 bg-white px-2 text-sm"
      >
        <option value="">미정</option>
        {choices.map((a) => (
          <option key={a.code} value={a.code}>
            {a.name} ({a.code})
          </option>
        ))}
      </select>
    </label>
  )
  return (
    <div className="rounded-xl bg-gray-50 px-3 py-1 text-sm">
      <div className="flex flex-wrap items-center gap-x-4">
        <span aria-hidden>✈️</span>
        {select('arrival_airport', '도착')}
        {select('departure_airport', '출발')}
      </div>
      <p className="pb-1 text-[11px] text-gray-500">
        첫날은 도착 공항에서 시작하고 마지막 날은 출발 공항에서 끝납니다. 항공편을 확정하면 그
        항공편 기준이 됩니다. 바꾼 뒤 다시 맞추기를 눌러 주세요.
      </p>
    </div>
  )
}
