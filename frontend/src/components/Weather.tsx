import type { WeatherOut } from '../api/client'
import { weatherLine } from '../lib/weather'

/** Sky = data fetched automatically. Climate figures are labeled 평년; Open-Meteo asks for attribution. */
export function WeatherChip({ w, compact = false }: { w: WeatherOut; compact?: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-xs ${w.rainy ? 'bg-sky-600 text-white' : 'bg-sky-50 text-sky-900 ring-1 ring-sky-200'}`}
      title={w.kind === 'climate' ? `지난 ${w.years ?? ''}년 같은 날짜 평균` : '예보 (Open-Meteo)'}
    >
      {compact ? weatherLine(w).split(' · ')[0] : weatherLine(w)}
    </span>
  )
}

export function WeatherCredit() {
  return (
    <a
      href="https://open-meteo.com/"
      target="_blank"
      rel="noreferrer"
      className="text-[11px] text-gray-400 underline-offset-2 hover:underline"
    >
      Weather data by Open-Meteo.com
    </a>
  )
}
