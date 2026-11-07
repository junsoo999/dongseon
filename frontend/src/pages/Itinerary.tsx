import { useState } from 'react'
import { Link } from 'react-router'
import type { DayOut, ItemOut, ItineraryOut } from '../api/client'
import {
  useActiveItinerary,
  useEditItinerary,
  useResolveItinerary,
  useRestoreItinerary,
  useSolveItinerary,
} from '../api/hooks'
import { DayMap } from '../components/DayMap'
import { HoursSheet } from '../components/HoursSheet'
import { LoadingBlock } from '../components/Loading'
import { MapLayout, Page } from '../components/MapLayout'
import { VersionsSheet } from '../components/VersionsSheet'
import { dayLabel } from '../lib/airlines'
import { directionsUrl, moveLabel } from '../lib/itinerary'
import {
  addPin,
  draftOf,
  moveToDay,
  moveWithin,
  removePin,
  sameDraft,
  toEditIn,
  toggleLock,
  type Draft,
} from '../lib/itineraryEdit'
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

function Rail() {
  return (
    <>
      <span className="w-12 shrink-0" />
      <span className="flex w-8 shrink-0 justify-center">
        <span className="h-6 border-l-2 border-dashed border-teal-300" />
      </span>
    </>
  )
}

function MoveRow({ item }: { item: ItemOut }) {
  const label = moveLabel(item.move_min, item.move_mode)
  if (!label) return null
  return (
    <li className="flex items-center gap-3">
      <Rail />
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

function Tags({ item }: { item: Pick<ItemOut, 'kind' | 'priority'> }) {
  return (
    <>
      {item.kind === 'meal' && (
        <span className="rounded bg-orange-50 px-1 text-[11px] text-orange-700">식사</span>
      )}
      {item.priority === 'must' && isPriority(item.priority) && (
        <span className="rounded bg-red-50 px-1 text-[11px] text-red-700">
          {PRIORITY_LABELS[item.priority]}
        </span>
      )}
    </>
  )
}

function VisitRow({ item, n, onHours }: { item: ItemOut; n: number; onHours: () => void }) {
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
          <Tags item={item} />
          {item.locked && (
            <span className="ml-auto text-xs" title="잠금: 다시 맞춰도 이 날짜·순서 유지">
              🔒
            </span>
          )}
        </p>
        <p className="flex items-center justify-between gap-2 text-xs text-gray-500">
          <span>🕘 {item.hours ?? '영업시간 정보 없음'}</span>
          {item.pin_id !== null && (
            <button
              type="button"
              onClick={onHours}
              className="shrink-0 rounded-lg px-1.5 py-1 font-medium text-teal-700 hover:bg-teal-50"
            >
              영업시간 입력
            </button>
          )}
        </p>
        <Warnings items={item.warnings} />
      </div>
    </li>
  )
}

function DayTimeline({ day, onHours }: { day: DayOut; onHours: (item: ItemOut) => void }) {
  return (
    <div className="space-y-3">
      <Warnings items={day.warnings} />
      <ol className="space-y-2">
        <StayRow time={day.start} text={`${day.depot}에서 출발`} />
        {day.items.map((item, i) => (
          <FragmentRows key={item.id} item={item} n={i + 1} onHours={() => onHours(item)} />
        ))}
        {day.back_at && (
          <>
            {day.back_move_min ? (
              <li className="flex items-center gap-3">
                <Rail />
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

function FragmentRows({ item, n, onHours }: { item: ItemOut; n: number; onHours: () => void }) {
  return (
    <>
      <MoveRow item={item} />
      <VisitRow item={item} n={n} onHours={onHours} />
    </>
  )
}

type PinInfo = { label: string; category: string | null; kind: string; priority: string | null }

function pinInfo(it: ItineraryOut): Map<number, PinInfo> {
  const out = new Map<number, PinInfo>()
  for (const x of it.dropped)
    out.set(x.pin_id, { label: x.label, category: null, kind: 'visit', priority: x.priority })
  for (const d of it.days)
    for (const i of d.items)
      if (i.pin_id !== null)
        out.set(i.pin_id, {
          label: i.label,
          category: i.category,
          kind: i.kind,
          priority: i.priority,
        })
  return out
}

const ICON_BTN =
  'flex size-11 shrink-0 items-center justify-center rounded-xl bg-teal-50 text-teal-800 ring-1 ring-teal-200 hover:bg-teal-100 disabled:opacity-40'

function EditDay({
  it,
  draft,
  dayIdx,
  onChange,
}: {
  it: ItineraryOut
  draft: Draft
  dayIdx: number
  onChange: (d: Draft) => void
}) {
  const info = pinInfo(it)
  const day = draft.days[dayIdx]
  const placed = new Set(draft.days.flatMap((d) => d.pinIds))
  const left = [...info.keys()].filter((p) => !placed.has(p))
  return (
    <div className="space-y-3">
      {day.pinIds.length === 0 && (
        <p className="text-sm text-gray-500">이 날은 비어 있습니다. 아래에서 넣을 수 있습니다.</p>
      )}
      <ol className="space-y-2">
        {day.pinIds.map((pinId, i) => {
          const p = info.get(pinId)
          const locked = draft.locked.includes(pinId)
          return (
            <li key={pinId} className="space-y-2 rounded-2xl border border-teal-200 bg-white p-3">
              <p className="flex items-center gap-1.5">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-teal-700 text-xs font-bold text-white">
                  {i + 1}
                </span>
                <span>{CATEGORY_EMOJI[p?.category ?? ''] ?? '📍'}</span>
                <span className="truncate font-medium">{p?.label ?? `장소 ${pinId}`}</span>
                {p && <Tags item={p} />}
              </p>
              <div className="flex flex-wrap items-center gap-1.5">
                <button
                  type="button"
                  aria-label="위로"
                  disabled={i === 0}
                  onClick={() => onChange(moveWithin(draft, pinId, -1))}
                  className={ICON_BTN}
                >
                  ↑
                </button>
                <button
                  type="button"
                  aria-label="아래로"
                  disabled={i === day.pinIds.length - 1}
                  onClick={() => onChange(moveWithin(draft, pinId, 1))}
                  className={ICON_BTN}
                >
                  ↓
                </button>
                <button
                  type="button"
                  aria-pressed={locked}
                  aria-label={locked ? '잠금 해제' : '잠금'}
                  onClick={() => onChange(toggleLock(draft, pinId))}
                  className={`${ICON_BTN} ${locked ? 'bg-teal-700 text-white ring-teal-700 hover:bg-teal-800' : ''}`}
                >
                  {locked ? '🔒' : '🔓'}
                </button>
                <select
                  aria-label="다른 날로 옮기기"
                  value=""
                  onChange={(e) =>
                    e.target.value && onChange(moveToDay(draft, pinId, e.target.value))
                  }
                  className="min-h-11 min-w-0 flex-1 rounded-xl bg-teal-50 px-2 text-sm text-teal-800 ring-1 ring-teal-200"
                >
                  <option value="">다른 날로…</option>
                  {draft.days.map((d, j) =>
                    j === dayIdx ? null : (
                      <option key={d.date} value={d.date}>
                        {j + 1}일차 · {dayLabel(`${d.date}T00:00`)}
                      </option>
                    ),
                  )}
                </select>
                <button
                  type="button"
                  onClick={() => onChange(removePin(draft, pinId))}
                  className="min-h-11 rounded-xl px-3 text-sm font-medium text-red-700 hover:bg-red-50"
                >
                  빼기
                </button>
              </div>
            </li>
          )
        })}
      </ol>
      {left.length > 0 && (
        <div className="space-y-1 rounded-2xl border border-gray-200 bg-white p-3">
          <p className="text-sm font-semibold">일정에 없는 곳 {left.length}곳</p>
          <ul className="space-y-1 text-sm">
            {left.map((pinId) => (
              <li key={pinId} className="flex items-center justify-between gap-2">
                <span className="truncate">{info.get(pinId)?.label}</span>
                <button
                  type="button"
                  onClick={() => onChange(addPin(draft, pinId, day.date))}
                  className="min-h-11 shrink-0 rounded-xl px-2 font-medium text-teal-700 hover:bg-teal-50"
                >
                  + {dayIdx + 1}일차에 넣기
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export function Itinerary() {
  const { trip, trips } = useCurrentTrip()
  const tripId = trip?.id ?? null
  const active = useActiveItinerary(tripId)
  const solve = useSolveItinerary(tripId)
  const edit = useEditItinerary(tripId)
  const resolve = useResolveItinerary(tripId)
  const restore = useRestoreItinerary(tripId)
  const [dayIdx, setDayIdx] = useState(0)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [hoursFor, setHoursFor] = useState<{ item: ItemOut; date: string } | null>(null)
  const [versionsOpen, setVersionsOpen] = useState(false)

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
  const idx = Math.min(dayIdx, (it?.days.length ?? 1) - 1)
  const day = it?.days[idx]
  const center =
    trip.center_lat !== null && trip.center_lng !== null
      ? { lat: trip.center_lat, lng: trip.center_lng }
      : { lat: 35.681, lng: 139.767 }
  const visits = it ? it.days.reduce((n, d) => n + d.items.length, 0) : 0
  const lockedCount = it
    ? it.days.reduce((n, d) => n + d.items.filter((x) => x.locked).length, 0)
    : 0
  const busy = solve.isPending || edit.isPending || resolve.isPending || restore.isPending
  const error = solve.error ?? edit.error ?? resolve.error ?? restore.error
  const dirty = !!(it && draft && !sameDraft(draft, draftOf(it)))

  const saveDraft = (andResolve: boolean) => {
    if (!it || !draft) return
    edit.mutate(
      { id: it.id, body: toEditIn(draft, andResolve) },
      { onSuccess: () => setDraft(null) },
    )
  }
  const retime = () => {
    // After the hours change, time the same layout again so the warnings update.
    setHoursFor(null)
    if (it) edit.mutate({ id: it.id, body: toEditIn(draftOf(it)) })
  }

  return (
    <MapLayout map={<DayMap items={day?.items ?? []} center={center} />}>
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-bold">날짜별 일정</h1>
          <p className="text-xs text-gray-500">
            {it ? (
              <>
                <button
                  type="button"
                  onClick={() => setVersionsOpen(true)}
                  className="font-semibold text-teal-700 underline-offset-2 hover:underline"
                >
                  버전 {it.version} ▾
                </button>{' '}
                · 방문 {visits}곳{lockedCount > 0 ? ` · 잠금 ${lockedCount}곳` : ''} · 이동시간은
                근사
              </>
            ) : (
              '장소·숙소·항공을 바탕으로 동선을 짭니다'
            )}
          </p>
        </div>
        {!it && (
          <button
            type="button"
            disabled={busy}
            onClick={() => solve.mutate()}
            className={`${BTN.primary} shrink-0`}
          >
            {solve.isPending ? '계산 중…' : '일정 초안 만들기'}
          </button>
        )}
      </div>

      {it && !draft && (
        <div className="space-y-1">
          <div className="flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => setDraft(draftOf(it))}
              className={`${BTN.soft} flex-1`}
            >
              ✏️ 편집
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => resolve.mutate(it.id)}
              className={`${BTN.primary} flex-1`}
            >
              다시 맞추기
            </button>
          </div>
          <p className="flex flex-wrap items-center justify-between gap-x-2 text-[11px] text-gray-500">
            <span>
              {lockedCount > 0
                ? `잠금 ${lockedCount}곳은 그대로 두고 나머지를 다시 맞춥니다`
                : '바뀐 영업시간·장소를 반영해 다시 맞춥니다'}
            </span>
            <button
              type="button"
              disabled={busy}
              onClick={() => solve.mutate()}
              className="min-h-8 font-medium text-teal-700 hover:underline"
            >
              잠금 무시하고 처음부터
            </button>
          </p>
        </div>
      )}

      {it && draft && (
        <div className="sticky top-0 z-10 space-y-2 rounded-2xl border border-teal-300 bg-teal-50 p-3">
          <p className="text-sm text-teal-900">
            <span className="font-semibold">편집 중</span> · 옮긴 곳은 자동으로 잠깁니다. 저장하면
            새 버전이 됩니다.
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => setDraft(null)}
              className={`${BTN.soft} bg-white`}
            >
              취소
            </button>
            <button
              type="button"
              disabled={busy || !dirty}
              onClick={() => saveDraft(false)}
              className={`${BTN.primary} flex-1`}
            >
              저장
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => saveDraft(true)}
              className={`${BTN.primary} flex-1`}
            >
              저장하고 나머지 다시 맞추기
            </button>
          </div>
        </div>
      )}
      {error && <p className="text-sm text-red-700">{error.message}</p>}

      {busy ? (
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
              const on = i === idx
              const warn = d.warnings.length > 0 || d.items.some((x) => x.warnings.length > 0)
              const count = draft ? draft.days[i].pinIds.length : d.items.length
              return (
                <button
                  key={d.date}
                  type="button"
                  role="tab"
                  aria-selected={on}
                  onClick={() => setDayIdx(i)}
                  className={`relative min-h-12 shrink-0 rounded-xl px-3 text-left text-sm ${on ? 'bg-teal-700 font-semibold text-white' : 'border border-gray-200 bg-white text-gray-700'}`}
                >
                  <span className="block text-[11px] opacity-80">
                    {i + 1}일차 · {count}곳
                  </span>
                  {dayLabel(`${d.date}T00:00`)}
                  {warn && !draft && (
                    <span className="absolute top-1 right-1 size-2 rounded-full bg-amber-400" />
                  )}
                </button>
              )
            })}
          </div>
          {draft ? (
            <EditDay it={it} draft={draft} dayIdx={idx} onChange={setDraft} />
          ) : (
            day && (
              <DayTimeline day={day} onHours={(item) => setHoursFor({ item, date: day.date })} />
            )
          )}
          {!draft && it.dropped.length > 0 && (
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
              <p className="text-[11px] text-gray-400">
                편집에서 원하는 날에 직접 넣을 수 있습니다.
              </p>
            </div>
          )}
          <p className="text-[11px] text-gray-400">
            시각은 모두 추정입니다. 이동시간은 직선거리 근사이고, 영업시간은 출처와 함께 표시합니다.
            실제 이동은 '길찾기'로 Google 지도에서 확인하세요.
          </p>
        </>
      )}

      {hoursFor && (
        <HoursSheet
          tripId={trip.id}
          item={hoursFor.item}
          date={hoursFor.date}
          onClose={() => setHoursFor(null)}
          onSaved={retime}
        />
      )}
      {versionsOpen && it && (
        <VersionsSheet
          tripId={trip.id}
          current={it}
          restoring={restore.isPending}
          onRestore={(id) => restore.mutate(id, { onSuccess: () => setVersionsOpen(false) })}
          onClose={() => setVersionsOpen(false)}
        />
      )}
    </MapLayout>
  )
}
