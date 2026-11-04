import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import type { TripOut } from '../api/client'
import {
  useFares,
  useFlights,
  useHotels,
  usePins,
  useStays,
  useStayScore,
  useSuggestions,
  useUsage,
} from '../api/hooks'
import { BottomSheet } from '../components/BottomSheet'
import { CreateTripForm } from '../components/CreateTripForm'
import { formatKrw } from '../lib/format'
import { buildTodos, countdownLabel, tripCountdown } from '../lib/home'
import { CATEGORY_EMOJI, categoryLabel } from '../lib/places'
import { BADGE, BTN, PANEL } from '../lib/theme'
import { todayIso, useCurrentTrip } from '../lib/trip'

const SHORTCUTS = [
  { to: '/places', icon: '📍', label: '장소', hint: '가고 싶은 곳·AI 추천' },
  { to: '/stays', icon: '🏨', label: '숙소', hint: '동네 순위·빈방' },
  { to: '/flights', icon: '✈️', label: '항공', hint: '실시간 운임·후보 비교' },
  { to: '/itinerary', icon: '🗓️', label: '일정', hint: '날짜별 동선' },
  { to: '/prep', icon: '🧳', label: '준비', hint: '체크리스트·예약' },
  { to: '/settings', icon: '⚙️', label: '설정', hint: '키·사용량' },
]

function Card({
  title,
  action,
  children,
  className = '',
}: {
  title: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section
      className={`rounded-2xl border border-gray-200 bg-white p-4 shadow-sm md:p-5 ${className}`}
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-[15px] font-semibold">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}

/** A loose Tokyo skyline (Mt Fuji, Tokyo Tower, Skytree, towers) as one faint layer behind the hero. */
function Skyline() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 800 160"
      preserveAspectRatio="xMidYMax slice"
      className="pointer-events-none absolute inset-x-0 bottom-0 h-28 w-full opacity-25 md:h-36"
    >
      <path d="M470 160 560 70l22 14 18-10 90 86z" fill="#fff" opacity="0.45" />
      <path d="M560 70l22 14 18-10-20-14z" fill="#fff" />
      <g fill="#fff">
        <rect x="16" y="96" width="36" height="64" rx="3" />
        <rect x="60" y="66" width="28" height="94" rx="3" />
        <rect x="96" y="104" width="44" height="56" rx="3" />
        <path d="M176 160l14-70h4l3-40h2l3 40h4l14 70h-10l-8-34h-8l-8 34z" />
        <rect x="236" y="84" width="40" height="76" rx="3" />
        <rect x="284" y="50" width="24" height="110" rx="3" />
        <rect x="316" y="100" width="50" height="60" rx="3" />
        <rect x="378" y="72" width="34" height="88" rx="3" />
        <path d="M430 160V44h4V8h2v-6h2v6h2v36h4v116z" />
        <rect x="456" y="92" width="36" height="68" rx="3" />
        <rect x="620" y="110" width="40" height="50" rx="3" />
        <rect x="668" y="62" width="26" height="98" rx="3" />
        <rect x="702" y="96" width="44" height="64" rx="3" />
        <rect x="752" y="80" width="32" height="80" rx="3" />
      </g>
      <path
        d="M0 150c80-10 160 10 240 0s160-12 240-2 160 12 320-2v14H0z"
        fill="#fff"
        opacity="0.6"
      />
    </svg>
  )
}

function Stat({
  label,
  value,
  sub,
  to,
}: {
  label: string
  value: string
  sub?: string
  to: string
}) {
  return (
    <Link
      to={to}
      className="rounded-2xl bg-white/15 px-3 py-2.5 backdrop-blur-sm transition hover:bg-white/25"
    >
      <div className="text-[11px] text-white/80">{label}</div>
      <div className="truncate text-[17px] leading-tight font-bold">{value}</div>
      {sub && <div className="truncate text-[11px] text-white/75">{sub}</div>}
    </Link>
  )
}

function Hero({ trip, onNew }: { trip: TripOut | null; onNew: () => void }) {
  const tripId = trip?.id ?? null
  const pins = usePins(tripId)
  const score = useStayScore(tripId)
  const fares = useFares(tripId)
  const hotels = useHotels(tripId)
  const stays = useStays(tripId)
  const countdown = trip ? tripCountdown(trip.start_date, trip.end_date, todayIso()) : null
  const all = pins.data ?? []
  const must = all.filter((p) => p.priority === 'must').length
  const cheapest = (fares.data?.items ?? []).find((f) => f.cheapest)
  const topArea = (score.data?.origins ?? []).find((o) => o.kind === 'area' && o.rank === 1)
  const booked = (stays.data ?? []).find((s) => s.status === 'booked')
  const lowestNight = (hotels.data?.areas ?? [])
    .flatMap((a) => a.items.map((v) => ({ area: a.area, krw: v.nightly_krw })))
    .filter((x): x is { area: string; krw: number } => x.krw !== null)
    .sort((a, b) => a.krw - b.krw)[0]

  return (
    <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-teal-600 via-sky-600 to-indigo-700 px-5 pt-5 pb-20 text-white shadow-lg md:px-8 md:pt-8 md:pb-24">
      <Skyline />
      <div className="relative flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
        <div className="flex items-center gap-4">
          <img
            src="/icon.svg"
            alt=""
            className="size-16 rounded-2xl shadow-xl ring-4 ring-white/25 md:size-20"
          />
          <div className="min-w-0">
            <h1 className="text-3xl font-extrabold tracking-tight md:text-4xl">dongseon</h1>
            <p className="truncate text-sm text-white/85 md:text-base">
              {trip ? `${trip.title} · ${trip.city_name}` : '가고 싶은 곳을 모아 날짜별 동선으로'}
            </p>
          </div>
        </div>
        {trip && countdown ? (
          <div className="md:text-right">
            <div className="text-4xl leading-none font-extrabold tracking-tight md:text-5xl">
              {countdownLabel(countdown)}
            </div>
            <div className="mt-1 text-sm text-white/85">
              {trip.start_date} ~ {trip.end_date}
              {countdown.kind === 'during' && ` · 총 ${countdown.total}일`}
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={onNew}
            className="rounded-xl bg-white px-4 py-3 font-semibold text-teal-800 shadow"
          >
            + 첫 여행 만들기
          </button>
        )}
      </div>
      {trip && (
        <div className="relative mt-5 grid grid-cols-2 gap-2 md:grid-cols-4">
          <Stat
            label="가고 싶은 곳"
            value={`${all.length}곳`}
            sub={must ? `꼭 ${must}곳` : '꼭 갈 곳을 정해 주세요'}
            to="/places"
          />
          <Stat
            label="최저 항공권"
            value={cheapest?.total_krw != null ? formatKrw(cheapest.total_krw) : '-'}
            sub={
              cheapest ? `${cheapest.route.replace('-', '→')} · 일행 합계` : '실시간 운임 가져오기'
            }
            to="/flights"
          />
          <Stat
            label="묵기 좋은 동네"
            value={topArea ? `${topArea.emoji ?? ''} ${topArea.label}` : '-'}
            sub={
              topArea?.weighted_avg_min != null
                ? `평균 ${topArea.weighted_avg_min}분 (근사)`
                : '꼭 갈 곳 기준'
            }
            to="/stays"
          />
          <Stat
            label="숙소"
            value={booked ? booked.label : lowestNight ? `${formatKrw(lowestNight.krw)}~` : '-'}
            sub={
              booked
                ? '예약 확정'
                : lowestNight
                  ? `1박 최저 · ${lowestNight.area}`
                  : '후보를 골라 주세요'
            }
            to="/stays"
          />
        </div>
      )}
    </section>
  )
}

function SuggestionsCard({ tripId, className = '' }: { tripId: number; className?: string }) {
  const suggestions = useSuggestions(tripId, 'place')
  const list = (suggestions.data ?? []).slice(0, 4)
  return (
    <section className={`${PANEL.ai} p-4 md:p-5 ${className}`}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-[15px] font-semibold">
          AI 추천 <span className={BADGE.ai}>AI 제안</span>
        </h2>
        <Link to="/places" className="text-sm font-medium text-violet-700">
          모두 보기 →
        </Link>
      </div>
      {list.length === 0 ? (
        <div className="flex items-center justify-between gap-3 rounded-xl bg-white p-3">
          <p className="text-sm text-gray-600">
            아직 추천이 없습니다. 장소 화면에서 '새로 찾기'를 눌러 보세요.
          </p>
          <Link to="/places" className={`${BTN.ai} shrink-0 px-3`}>
            찾으러 가기
          </Link>
        </div>
      ) : (
        <ol className="space-y-2">
          {list.map((s, i) => {
            const p = s.place
            if (!p) return null
            return (
              <li key={s.id} className="flex gap-3 rounded-xl bg-white p-3">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-violet-50 text-xl">
                  {CATEGORY_EMOJI[p.category] ?? '📍'}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="flex items-baseline gap-2">
                    <span className="text-sm font-bold text-violet-700">{i + 1}</span>
                    <span className="truncate font-medium">{p.name}</span>
                  </p>
                  <p className="text-xs text-gray-500">
                    {p.area} · {categoryLabel(p.category)}
                    {p.price_range && ` · ${p.price_range}`}
                  </p>
                  <p className="mt-0.5 line-clamp-2 text-sm text-gray-700">{p.why}</p>
                </div>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}

function TodoCard({ trip, className = '' }: { trip: TripOut; className?: string }) {
  const pins = usePins(trip.id)
  const flights = useFlights(trip.id)
  const stays = useStays(trip.id)
  const suggestions = useSuggestions(trip.id, 'place')
  const usage = useUsage()
  const countdown = tripCountdown(trip.start_date, trip.end_date, todayIso())
  const all = pins.data ?? []
  const todos = buildTodos({
    pins: all.length,
    mustPins: all.filter((p) => p.priority === 'must').length,
    unresolvedPins: all.filter((p) => p.resolve_status !== 'ok').length,
    bookedFlight: (flights.data ?? []).some((f) => f.status === 'booked'),
    flightCandidates: (flights.data ?? []).length,
    bookedStay: (stays.data ?? []).some((s) => s.status === 'booked'),
    stayCandidates: (stays.data ?? []).length,
    pendingSuggestions: (suggestions.data ?? []).length,
    daysToStart: countdown.kind === 'before' ? countdown.days : null,
    googleWarnSkus: (usage.data?.skus ?? []).filter((s) => s.level !== 'ok').map((s) => s.sku),
  })
  return (
    <Card title="할 일" className={className}>
      {todos.length === 0 ? (
        <p className="text-sm text-gray-600">지금은 할 일이 없습니다. 🎉</p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {todos.map((t) => (
            <li key={t.text}>
              <Link to={t.to} className="flex min-h-11 items-center gap-2 py-2 text-sm">
                <span aria-hidden>{t.tone === 'warn' ? '⚠️' : '👉'}</span>
                <span
                  className={`flex-1 ${t.tone === 'warn' ? 'text-amber-800' : 'text-gray-800'}`}
                >
                  {t.text}
                </span>
                <span className="text-gray-400">›</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function PricesCard({ tripId, className = '' }: { tripId: number; className?: string }) {
  const fares = useFares(tripId)
  const hotels = useHotels(tripId)
  const byRoute = new Map<string, number>()
  for (const f of fares.data?.items ?? []) {
    const v = f.total_krw ?? f.amount
    if (!byRoute.has(f.route) || v < (byRoute.get(f.route) ?? Infinity)) byRoute.set(f.route, v)
  }
  const areas = (hotels.data?.areas ?? []).map((a) => ({
    label: `${a.emoji ?? ''} ${a.area}`,
    min: Math.min(...a.items.map((v) => v.nightly_krw ?? Infinity)),
  }))
  return (
    <section className={`${PANEL.live} p-4 md:p-5 ${className}`}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-[15px] font-semibold">
          오늘의 최저가 <span className={BADGE.live}>자동 수집</span>
        </h2>
        <span className="text-xs text-gray-500">매일 06:00 갱신</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Link to="/flights" className="rounded-xl bg-white p-3">
          <p className="mb-1 text-xs font-medium text-sky-800">✈️ 왕복 항공권 (일행 합계)</p>
          {byRoute.size === 0 ? (
            <p className="text-sm text-gray-500">아직 없음</p>
          ) : (
            [...byRoute].map(([route, v]) => (
              <p key={route} className="flex justify-between text-sm">
                <span className="text-gray-600">{route.replace('-', ' → ')}</span>
                <span className="font-semibold">{formatKrw(v)}</span>
              </p>
            ))
          )}
        </Link>
        <Link to="/stays" className="rounded-xl bg-white p-3">
          <p className="mb-1 text-xs font-medium text-sky-800">🏨 楽天トラベル 1박 최저 (2인)</p>
          {areas.length === 0 ? (
            <p className="text-sm text-gray-500">아직 없음</p>
          ) : (
            areas.map((a) => (
              <p key={a.label} className="flex justify-between text-sm">
                <span className="text-gray-600">{a.label}</span>
                <span className="font-semibold">
                  {Number.isFinite(a.min) ? formatKrw(a.min) : '-'}
                </span>
              </p>
            ))
          )}
        </Link>
      </div>
    </section>
  )
}

function TripsCard({
  trips,
  current,
  onPick,
  onNew,
}: {
  trips: TripOut[]
  current: TripOut | null
  onPick: (id: number) => void
  onNew: () => void
}) {
  return (
    <Card
      title="여행"
      action={
        <button type="button" onClick={onNew} className={`${BTN.primary} min-h-9 px-3 text-xs`}>
          + 새 여행
        </button>
      }
    >
      <ul className="space-y-1.5">
        {trips.map((t) => (
          <li key={t.id}>
            <button
              type="button"
              onClick={() => onPick(t.id)}
              className={`flex min-h-12 w-full items-center justify-between rounded-xl px-3 py-2 text-left ${t.id === current?.id ? 'bg-teal-50 ring-1 ring-teal-200' : 'hover:bg-gray-50'}`}
            >
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium">{t.title}</span>
                <span className="block text-xs text-gray-500">
                  {t.city_name} · {t.start_date} ~ {t.end_date} · 장소 {t.pin_count}곳
                </span>
              </span>
              {t.id === current?.id && (
                <span className="text-xs font-semibold text-teal-700">보는 중</span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </Card>
  )
}

export function Home() {
  const { trips, trip, setTripId } = useCurrentTrip()
  const [creating, setCreating] = useState(false)
  const list = trips.data ?? []

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4 p-4 md:gap-5 md:p-6">
      <Hero trip={trip} onNew={() => setCreating(true)} />
      {trip && (
        <>
          <div className="grid gap-4 md:grid-cols-3 md:gap-5">
            <SuggestionsCard tripId={trip.id} className="md:col-span-2" />
            <TodoCard trip={trip} />
          </div>
          <div className="grid gap-4 md:grid-cols-3 md:gap-5">
            <PricesCard tripId={trip.id} className="md:col-span-2" />
            <TripsCard
              trips={list}
              current={trip}
              onPick={setTripId}
              onNew={() => setCreating(true)}
            />
          </div>
        </>
      )}
      <nav
        aria-label="바로가기"
        className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-6 md:gap-3"
      >
        {SHORTCUTS.map((s) => (
          <Link
            key={s.to}
            to={s.to}
            className="group flex min-h-16 items-center gap-3 rounded-2xl border border-gray-200 bg-white px-4 py-3 shadow-sm transition hover:-translate-y-0.5 hover:border-teal-300 hover:shadow-md"
          >
            <span className="text-2xl transition group-hover:scale-110" aria-hidden="true">
              {s.icon}
            </span>
            <span className="min-w-0">
              <span className="block font-medium">{s.label}</span>
              <span className="block truncate text-xs text-gray-600">{s.hint}</span>
            </span>
          </Link>
        ))}
      </nav>
      <BottomSheet open={creating} title="새 여행" onClose={() => setCreating(false)}>
        <CreateTripForm
          onDone={(id) => {
            setTripId(id)
            setCreating(false)
          }}
        />
      </BottomSheet>
    </div>
  )
}
