import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import type { FxOut, ItemOut, OfflineOut, OfflineStopOut } from '../api/client'
import { useToday } from '../api/hooks'
import { HoursAlert } from '../components/HoursAlert'
import { Page } from '../components/MapLayout'
import { WeatherChip, WeatherCredit } from '../components/Weather'
import { dayLabel } from '../lib/airlines'
import { formatMoney } from '../lib/format'
import { directionsUrl } from '../lib/itinerary'
import { CATEGORY_EMOJI } from '../lib/places'
import { BTN } from '../lib/theme'
import { isUnreachable, savedAtLabel } from '../lib/offline'
import { clockIn, dateIn, nowAndNext } from '../lib/today'
import { useCurrentTrip } from '../lib/trip'
import { useOffline } from '../lib/useOffline'

/** The current time, refreshed every 30 s so "지금" follows the clock. */
function useNow(): Date {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 30_000)
    return () => window.clearInterval(t)
  }, [])
  return now
}

function useClock(timeZone: string | undefined): string {
  const now = useNow()
  return timeZone ? clockIn(timeZone, now) : ''
}

type CardStop = {
  label: string
  start: string
  end: string
  warnings: string[]
  hours?: string | null
  emoji?: string
  href: string
}

function StopCard({ stop, tag, strong }: { stop: CardStop; tag: string; strong?: boolean }) {
  return (
    <section
      className={`space-y-2 rounded-2xl border p-4 ${strong ? 'border-teal-300 bg-teal-50' : 'border-gray-200 bg-white'}`}
    >
      <p className="text-xs font-semibold text-teal-800">
        {tag} · {stop.start}~{stop.end} <span className="font-normal text-gray-500">(예상)</span>
      </p>
      <p className="text-lg font-bold">
        {stop.emoji ?? '📍'} {stop.label}
      </p>
      {stop.hours && <p className="text-xs text-gray-500">영업 {stop.hours}</p>}
      {stop.warnings.length > 0 && (
        <p className="text-xs text-amber-800">⚠️ {stop.warnings.join(' · ')}</p>
      )}
      <a href={stop.href} target="_blank" rel="noreferrer" className={`${BTN.primary} w-full`}>
        Google 지도로 길찾기
      </a>
    </section>
  )
}

function itemCard(i: ItemOut): CardStop {
  return { ...i, emoji: CATEGORY_EMOJI[i.category ?? ''], href: directionsUrl(i) }
}

function offlineCard(s: OfflineStopOut): CardStop {
  return { ...s, href: s.directions_url }
}

function StopRow({
  label,
  start,
  href,
  past,
}: {
  label: string
  start: string
  href: string
  past: boolean
}) {
  return (
    <li
      className={`flex items-center gap-3 rounded-xl border border-gray-200 bg-white px-3 py-2 ${past ? 'opacity-50' : ''}`}
    >
      <span className="w-11 shrink-0 text-sm font-semibold tabular-nums">{start}</span>
      <span className="min-w-0 flex-1 truncate text-sm">{label}</span>
      <a
        href={href}
        target="_blank"
        rel="noreferrer"
        aria-label={`${label} 길찾기`}
        className="flex min-h-11 shrink-0 items-center rounded-lg px-2 text-xs font-medium text-teal-700 hover:bg-teal-50"
      >
        길찾기
      </a>
    </li>
  )
}

/** The saved copy, for when the home Mac cannot be reached: any day, with now/next on today's date. */
function OfflineToday({ bundle }: { bundle: OfflineOut }) {
  const tz = bundle.trip.timezone
  const now = useNow()
  const hhmm = clockIn(tz, now)
  const today = dateIn(tz, now)
  const initial = bundle.days.find((d) => d.date === today)?.date ?? bundle.days[0]?.date ?? null
  const [picked, setPicked] = useState<string | null>(initial)
  const day = bundle.days.find((d) => d.date === picked) ?? null
  const isToday = day?.date === today
  const { current, next } = nowAndNext(day?.stops ?? [], isToday ? hhmm : '00:00')
  return (
    <Page>
      <div>
        <h1 className="text-xl font-bold">오늘 · 저장된 일정</h1>
        <p className="text-sm text-gray-500">
          {bundle.trip.title} · 현지 시각 {hhmm} · {savedAtLabel(bundle.generated_at)} 저장
          {bundle.version ? ` · v${bundle.version}` : ''}
        </p>
      </div>
      {bundle.days.length === 0 ? (
        <p className="text-sm text-gray-600">저장할 때 일정이 없었습니다.</p>
      ) : (
        <>
          <div className="flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="날짜">
            {bundle.days.map((d) => (
              <button
                key={d.date}
                role="tab"
                aria-selected={d.date === picked}
                onClick={() => setPicked(d.date)}
                className={`min-h-11 shrink-0 rounded-xl border px-3 text-sm ${d.date === picked ? 'border-teal-600 bg-teal-600 font-semibold text-white' : 'border-gray-300 bg-white text-gray-700'}`}
              >
                {dayLabel(`${d.date}T00:00`)}
              </button>
            ))}
          </div>
          {isToday && current && <StopCard stop={offlineCard(current)} tag="지금" strong />}
          {isToday && next && <StopCard stop={offlineCard(next)} tag="다음" strong={!current} />}
          {day && (
            <section className="space-y-2">
              <ol className="space-y-1">
                {day.stops.map((s) => (
                  <StopRow
                    key={s.seq}
                    label={s.label}
                    start={s.start}
                    href={s.directions_url}
                    past={isToday && s.end <= hhmm}
                  />
                ))}
              </ol>
              <p className="text-[11px] text-gray-400">
                {day.depot && `${day.depot}에서 출발 · `}시각은 모두 추정입니다. 길찾기는 연결이
                필요합니다.
              </p>
            </section>
          )}
        </>
      )}
    </Page>
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
  const { tripsDown, bundle } = useOffline()

  const unreachable = tripsDown || (today.isError && isUnreachable(today.error))
  if (unreachable && bundle) return <OfflineToday bundle={bundle} />
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
          {current && <StopCard stop={itemCard(current)} tag="지금" strong />}
          {next && <StopCard stop={itemCard(next)} tag="다음" strong={!current} />}
          {done && (
            <p className="rounded-2xl bg-gray-50 p-4 text-sm text-gray-600">
              오늘 일정을 모두 마쳤습니다.{' '}
              {t.day.end_place
                ? `${t.day.end_place} 도착 예상 시각은 ${t.day.back_at ?? '-'}입니다.`
                : `${t.day.depot}(으)로 돌아가는 시각은 ${t.day.back_at ?? '-'}(예상)입니다.`}
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
            {t.day.items.map((i) => (
              <StopRow
                key={i.id}
                label={i.label}
                start={i.start}
                href={directionsUrl(i)}
                past={during && i.end <= hhmm}
              />
            ))}
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
