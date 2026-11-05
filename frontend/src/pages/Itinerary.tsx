import { useState } from 'react'
import { Link } from 'react-router'
import type { DayOut, ItemOut } from '../api/client'
import { useActiveItinerary, useSolveItinerary } from '../api/hooks'
import { DayMap } from '../components/DayMap'
import { LoadingBlock } from '../components/Loading'
import { MapLayout, Page } from '../components/MapLayout'
import { dayLabel } from '../lib/airlines'
import { directionsUrl, moveLabel } from '../lib/itinerary'
import { CATEGORY_EMOJI, PRIORITY_LABELS, isPriority } from '../lib/places'
import { BTN } from '../lib/theme'
import { useCurrentTrip } from '../lib/trip'

function Warnings({ items }: { items: string[] }) {
  if (items.length === 0) return null
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((w) => (
        <span
          key={w}
          className="rounded-md bg-amber-50 px-1.5 py-0.5 text-[11px] text-amber-800 ring-1 ring-amber-200"
        >
          ⚠️ {w}
        </span>
      ))}
    </div>
  )
}

function StayRow({ time, text }: { time: string | null; text: string }) {
  return (
    <li className="flex items-center gap-3">
      <span className="w-12 shrink-0 text-right text-sm font-semibold tabular-nums text-gray-500">
        {time ?? ''}
      </span>
      <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-slate-100">
        🏨
      </span>
      <span className="text-sm text-gray-600">{text}</span>
    </li>
  )
}

function MoveRow({ item }: { item: ItemOut }) {
  const label = moveLabel(item.move_min, item.move_mode)
  if (!label) return null
  return (
    <li className="flex items-center gap-3">
      <span className="w-12 shrink-0" />
      <span className="flex w-8 shrink-0 justify-center">
        <span className="h-6 border-l-2 border-dashed border-teal-300" />
      </span>
      <span className="flex flex-1 items-center justify-between gap-2 text-xs text-gray-500">
        {label}
        <a
          href={directionsUrl(item, item.move_mode === 'walk' ? 'walking' : 'transit')}
          target="_blank"
          rel="noreferrer"
          className="rounded-lg px-2 py-1 font-medium text-teal-700 hover:bg-teal-50"
        >
          길찾기 ↗
        </a>
      </span>
    </li>
  )
}

function VisitRow({ item, n }: { item: ItemOut; n: number }) {
  return (
    <li className="flex gap-3">
      <span className="w-12 shrink-0 pt-2 text-right text-sm leading-tight font-semibold tabular-nums">
        {item.start}
        <span className="block text-[11px] font-normal text-gray-400">~{item.end}</span>
      </span>
      <span className="relative flex size-8 shrink-0 items-center justify-center rounded-full bg-teal-700 text-sm font-bold text-white">
        {n}
      </span>
      <div className="min-w-0 flex-1 space-y-1 rounded-2xl border border-gray-200 bg-white p-3 shadow-sm">
        <p className="flex items-center gap-1.5">
          <span>{CATEGORY_EMOJI[item.category ?? ''] ?? '📍'}</span>
          <span className="truncate font-medium">{item.label}</span>
          {item.kind === 'meal' && (
            <span className="rounded bg-orange-50 px-1 text-[11px] text-orange-700">식사</span>
          )}
          {item.priority && isPriority(item.priority) && item.priority === 'must' && (
            <span className="rounded bg-red-50 px-1 text-[11px] text-red-700">
              {PRIORITY_LABELS[item.priority]}
            </span>
          )}
        </p>
        {item.hours && <p className="text-xs text-gray-500">🕘 {item.hours}</p>}
        <Warnings items={item.warnings} />
      </div>
    </li>
  )
}

function DayTimeline({ day }: { day: DayOut }) {
  return (
    <div className="space-y-3">
      <Warnings items={day.warnings} />
      <ol className="space-y-2">
        <StayRow time={day.start} text={`${day.depot}에서 출발`} />
        {day.items.map((item, i) => (
          <FragmentRows key={item.id} item={item} n={i + 1} />
        ))}
        {day.back_at && (
          <>
            {day.back_move_min ? (
              <li className="flex items-center gap-3">
                <span className="w-12 shrink-0" />
                <span className="flex w-8 shrink-0 justify-center">
                  <span className="h-6 border-l-2 border-dashed border-teal-300" />
                </span>
                <span className="text-xs text-gray-500">
                  {moveLabel(day.back_move_min, 'rail')}
                </span>
              </li>
            ) : null}
            <StayRow time={day.back_at} text={`${day.depot} 도착 (하루 끝 ${day.end})`} />
          </>
        )}
      </ol>
      {day.items.length === 0 && <p className="text-sm text-gray-500">이 날은 일정이 없습니다.</p>}
    </div>
  )
}

function FragmentRows({ item, n }: { item: ItemOut; n: number }) {
  return (
    <>
      <MoveRow item={item} />
      <VisitRow item={item} n={n} />
    </>
  )
}

export function Itinerary() {
  const { trip, trips } = useCurrentTrip()
  const tripId = trip?.id ?? null
  const active = useActiveItinerary(tripId)
  const solve = useSolveItinerary(tripId)
  const [dayIdx, setDayIdx] = useState(0)

  if (trips.isPending) return <p className="p-4 text-gray-500">불러오는 중…</p>
  if (!trip) {
    return (
      <Page>
        <h1 className="text-xl font-bold">일정</h1>
        <Link to="/" className={BTN.primary}>
          홈에서 여행 만들기
        </Link>
      </Page>
    )
  }

  const it = active.data
  const day = it?.days[Math.min(dayIdx, (it?.days.length ?? 1) - 1)]
  const center =
    trip.center_lat !== null && trip.center_lng !== null
      ? { lat: trip.center_lat, lng: trip.center_lng }
      : { lat: 35.681, lng: 139.767 }
  const visits = it ? it.days.reduce((n, d) => n + d.items.length, 0) : 0

  return (
    <MapLayout map={<DayMap items={day?.items ?? []} center={center} />}>
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-bold">날짜별 일정</h1>
          <p className="text-xs text-gray-500">
            {it
              ? `버전 ${it.version} · 방문 ${visits}곳 · 이동시간은 근사`
              : '장소·숙소·항공을 바탕으로 동선을 짭니다'}
          </p>
        </div>
        <button
          type="button"
          disabled={solve.isPending}
          onClick={() => solve.mutate()}
          className={`${BTN.primary} shrink-0`}
        >
          {solve.isPending ? '계산 중…' : it ? '다시 만들기' : '일정 초안 만들기'}
        </button>
      </div>
      {solve.error && <p className="text-sm text-red-700">{solve.error.message}</p>}

      {solve.isPending ? (
        <LoadingBlock
          tone="live"
          title="동선을 계산하는 중…"
          hint="영업시간을 확인하고 날짜별로 순서를 맞춥니다 (몇 초)"
        />
      ) : !it ? (
        <div className="rounded-2xl border border-dashed border-gray-300 bg-white p-4 text-sm text-gray-600">
          아직 일정이 없습니다. 가고 싶은 곳에 우선순위·머무는 시간을 정하고, 숙소와 항공편을
          확정하면 더 정확해집니다.
        </div>
      ) : (
        <>
          <div role="tablist" className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1">
            {it.days.map((d, i) => {
              const on = i === dayIdx
              const warn = d.warnings.length > 0 || d.items.some((x) => x.warnings.length > 0)
              return (
                <button
                  key={d.date}
                  type="button"
                  role="tab"
                  aria-selected={on}
                  onClick={() => setDayIdx(i)}
                  className={`relative min-h-12 shrink-0 rounded-xl px-3 text-left text-sm ${on ? 'bg-teal-700 font-semibold text-white' : 'border border-gray-200 bg-white text-gray-700'}`}
                >
                  <span className="block text-[11px] opacity-80">{i + 1}일차</span>
                  {dayLabel(`${d.date}T00:00`)}
                  {warn && (
                    <span className="absolute top-1 right-1 size-2 rounded-full bg-amber-400" />
                  )}
                </button>
              )
            })}
          </div>
          {day && <DayTimeline day={day} />}
          {it.dropped.length > 0 && (
            <div className="space-y-1 rounded-2xl border border-gray-200 bg-white p-3">
              <p className="text-sm font-semibold">넣지 못한 곳 {it.dropped.length}곳</p>
              <ul className="space-y-1 text-sm">
                {it.dropped.map((x) => (
                  <li key={x.pin_id} className="flex justify-between gap-2">
                    <span className="truncate">
                      {x.label}
                      {isPriority(x.priority) && (
                        <span className="ml-1 text-xs text-gray-400">
                          {PRIORITY_LABELS[x.priority]}
                        </span>
                      )}
                    </span>
                    <span className="shrink-0 text-xs text-gray-500">{x.reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <p className="text-[11px] text-gray-400">
            시각은 모두 추정입니다. 이동시간은 직선거리 근사이고, 영업시간은 출처와 함께 표시합니다.
            실제 이동은 '길찾기'로 Google 지도에서 확인하세요.
          </p>
        </>
      )}
    </MapLayout>
  )
}
