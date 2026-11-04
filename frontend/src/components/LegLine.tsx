import { dayLabel, dayOffset } from '../lib/airlines'
import { formatMinutes } from '../lib/format'
import { directionMinutes, type LegSegment } from '../lib/legs'
import { AirlineLogo } from './AirlineLogo'

/** One direction as "logo  08:10 ──✈── 10:25" with airports, duration, stops, date and flight numbers. */
export function LegLine({ label, segs }: { label: string; segs: LegSegment[] }) {
  if (segs.length === 0) return null
  const first = segs[0]
  const last = segs[segs.length - 1]
  const stops = segs.length - 1
  const plusDays = dayOffset(first.depLocal, last.arrLocal)
  const carriers = Array.from(new Set(segs.map((s) => s.carrier).filter(Boolean)))
  const flights = segs
    .map((s) => s.flight)
    .filter(Boolean)
    .join(' / ')
  return (
    <div className="flex items-center gap-3">
      <AirlineLogo code={first.carrierCode} name={first.carrier} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <div className="text-center">
            <p className="text-lg leading-tight font-semibold tabular-nums">
              {first.depLocal.slice(11, 16)}
            </p>
            <p className="text-xs text-gray-500">{first.depAirport}</p>
          </div>
          <div className="min-w-0 flex-1 text-center">
            <p className="text-[11px] text-gray-500">{formatMinutes(directionMinutes(segs))}</p>
            <div className="relative my-1 h-px bg-gray-300">
              <span className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white px-1 text-xs leading-none">
                ✈️
              </span>
            </div>
            <p className={`text-[11px] ${stops ? 'text-amber-700' : 'text-gray-500'}`}>
              {stops
                ? `경유 ${stops}회 (${segs
                    .slice(0, -1)
                    .map((s) => s.arrAirport)
                    .join(', ')})`
                : '직항'}
            </p>
          </div>
          <div className="text-center">
            <p className="text-lg leading-tight font-semibold tabular-nums">
              {last.arrLocal.slice(11, 16)}
              {plusDays > 0 && <sup className="ml-0.5 text-[10px] text-amber-700">+{plusDays}</sup>}
            </p>
            <p className="text-xs text-gray-500">{last.arrAirport}</p>
          </div>
        </div>
        <p className="mt-0.5 truncate text-xs text-gray-500">
          <span className="font-medium text-gray-700">{label}</span>
          {' · '}
          {[dayLabel(first.depLocal), [carriers.join('·'), flights].filter(Boolean).join(' ')]
            .filter(Boolean)
            .join(' · ')}
        </p>
      </div>
    </div>
  )
}
