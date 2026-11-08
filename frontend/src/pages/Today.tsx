import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import type { FxOut, ItemOut } from '../api/client'
import { useToday } from '../api/hooks'
import { HoursAlert } from '../components/HoursAlert'
import { Page } from '../components/MapLayout'
import { WeatherChip, WeatherCredit } from '../components/Weather'
import { dayLabel } from '../lib/airlines'
import { formatMoney } from '../lib/format'
import { directionsUrl } from '../lib/itinerary'
import { CATEGORY_EMOJI } from '../lib/places'
import { BTN } from '../lib/theme'
import { clockIn, nowAndNext } from '../lib/today'
import { useCurrentTrip } from '../lib/trip'

/** Re-render every 30 s so "지금" follows the clock. */
function useClock(timeZone: string | undefined): string {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 30_000)
    return () => window.clearInterval(t)
  }, [])
  return timeZone ? clockIn(timeZone, now) : ''
}

function StopCard({ item, tag, strong }: { item: ItemOut; tag: string; strong?: boolean }) {
  return (
    <section
      className={`space-y-2 rounded-2xl border p-4 ${strong ? 'border-teal-300 bg-teal-50' : 'border-gray-200 bg-white'}`}
    >
      <p className="text-xs font-semibold text-teal-800">
        {tag} · {item.start}~{item.end} <span className="font-normal text-gray-500">(예상)</span>
      </p>
      <p className="text-lg font-bold">
        {CATEGORY_EMOJI[item.category ?? ''] ?? '📍'} {item.label}
      </p>
      {item.hours && <p className="text-xs text-gray-500">영업 {item.hours}</p>}
      {item.warnings.length > 0 && (
        <p className="text-xs text-amber-800">⚠️ {item.warnings.join(' · ')}</p>
      )}
      <a
        href={directionsUrl(item)}
        target="_blank"
        rel="noreferrer"
        className={`${BTN.primary} w-full`}
      >
        Google 지도로 길찾기
      </a>
    </section>
  )
}

function FxCalculator({ fx }: { fx: FxOut }) {
  const [yen, setYen] = useState('1000')
  const n = Number(yen.replace(/,/g, ''))
  return (
    <section className="space-y-2 rounded-2xl border border-gray-200 bg-white p-4">
      <p className="text-sm font-semibold">환율 계산</p>
      <label className="flex items-center gap-2">
        <span className="text-sm text-gray-500">¥</span>
        <input
          inputMode="numeric"
          value={yen}
          onChange={(e) => setYen(e.target.value)}
          aria-label="엔화 금액"
          className="min-h-11 w-full rounded-xl border border-gray-300 px-3 text-lg"
        />
      </label>
      <p className="text-2xl font-bold">
        {Number.isFinite(n) ? formatMoney(Math.round(n * fx.rate), 'KRW') : '-'}
      </p>
      <p className="text-[11px] text-gray-400">
        1 {fx.base} = {fx.rate} {fx.quote} · {fx.source}, {fx.date} 기준 (카드 결제 환율과 다를 수
        있음)
      </p>
    </section>
  )
}

export function Today() {
  const { trip, trips } = useCurrentTrip()
  const today = useToday(trip?.id ?? null)
  const hhmm = useClock(trip?.timezone)

  if (trips.isPending) return <p className="text-gray-500">불러오는 중…</p>
  if (!trip) {
    return (
      <Page>
        <h1 className="text-xl font-bold">오늘</h1>
        <Link to="/" className={BTN.primary}>
          홈에서 여행 만들기
        </Link>
      </Page>
    )
  }
  const t = today.data
  const items = t?.day?.items ?? []
  const { current, next, done } = nowAndNext(items, hhmm)
  const during = t?.phase === 'during'

  return (
    <Page>
      <div>
        <h1 className="text-xl font-bold">
          {!t
            ? '오늘'
            : during
              ? `오늘 · ${dayLabel(`${t.today}T00:00`)}`
              : t.phase === 'before'
                ? `출발까지 D-${t.days_until}`
                : '여행이 끝났습니다'}
        </h1>
        <p className="text-sm text-gray-500">
          {trip.title} · 현지 시각 {hhmm}
        </p>
      </div>
      {today.isError && <p className="text-sm text-red-700">{today.error.message}</p>}

      {t?.weather && (
        <p className="flex flex-wrap items-center gap-2">
          <WeatherChip w={t.weather} />
          <WeatherCredit />
        </p>
      )}
      {t?.itinerary_id && <HoursAlert tripId={trip.id} />}

      {t && !t.day && t.phase !== 'after' && (
        <div className="rounded-2xl border border-dashed border-gray-300 bg-white p-4 text-sm text-gray-600">
          아직 일정이 없습니다.{' '}
          <Link to="/itinerary" className="font-semibold text-teal-700 underline">
            일정에서 초안 만들기
          </Link>
        </div>
      )}

      {t?.day && during && (
        <>
          {current && <StopCard item={current} tag="지금" strong />}
          {next && <StopCard item={next} tag="다음" strong={!current} />}
          {done && (
            <p className="rounded-2xl bg-gray-50 p-4 text-sm text-gray-600">
              오늘 일정을 모두 마쳤습니다. {t.day.depot}(으)로 돌아가는 시각은{' '}
              {t.day.back_at ?? '-'}
              (예상)입니다.
            </p>
          )}
        </>
      )}

      {t?.day && (
        <section className="space-y-2">
          <p className="text-sm font-semibold">
            {during ? '오늘 전체' : `첫날 미리보기 · ${dayLabel(`${t.day.date}T00:00`)}`}
          </p>
          <ol className="space-y-1">
            {t.day.items.map((i) => {
              const past = during && i.end <= hhmm
              return (
                <li
                  key={i.id}
                  className={`flex items-center gap-3 rounded-xl border border-gray-200 bg-white px-3 py-2 ${past ? 'opacity-50' : ''}`}
                >
                  <span className="w-11 shrink-0 text-sm font-semibold tabular-nums">
                    {i.start}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-sm">{i.label}</span>
                  <a
                    href={directionsUrl(i)}
                    target="_blank"
                    rel="noreferrer"
                    aria-label={`${i.label} 길찾기`}
                    className="flex min-h-11 shrink-0 items-center rounded-lg px-2 text-xs font-medium text-teal-700 hover:bg-teal-50"
                  >
                    길찾기
                  </a>
                </li>
              )
            })}
          </ol>
          <p className="text-[11px] text-gray-400">
            시각은 모두 추정입니다. 실제 이동은 Google 지도에서 확인하세요.
          </p>
        </section>
      )}

      {t?.fx && <FxCalculator fx={t.fx} />}
    </Page>
  )
}
