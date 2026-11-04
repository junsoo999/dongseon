import { useState } from 'react'
import { Link } from 'react-router'
import { usePins } from '../api/hooks'
import { AddPlaceSheet } from '../components/AddPlaceSheet'
import { AiSuggestions } from '../components/AiSuggestions'
import { BottomSheet } from '../components/BottomSheet'
import { PinEditSheet } from '../components/PinEditSheet'
import { PlacesMap } from '../components/PlacesMap'
import { formatMinutes } from '../lib/format'
import {
  categoryLabel,
  CATEGORY_EMOJI,
  CATEGORY_LABELS,
  EMPTY_FILTER,
  filterPins,
  isPriority,
  MEAL_LABELS,
  PRIORITIES,
  PRIORITY_COLORS,
  PRIORITY_LABELS,
  sortPins,
  toggle,
  unresolvedPins,
  type PinFilter,
} from '../lib/places'
import { useCurrentTrip } from '../lib/trip'
import { MapLayout, Page } from '../components/MapLayout'

const DEFAULT_CENTER = { lat: 35.681, lng: 139.767 }

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: string
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`min-h-11 rounded-full border px-4 text-sm ${active ? 'border-teal-700 bg-teal-50 font-semibold text-teal-800' : 'border-gray-300'}`}
    >
      {children}
    </button>
  )
}

export function Places() {
  const { trip, trips } = useCurrentTrip()
  const tripId = trip?.id ?? null
  const pins = usePins(tripId)
  const [filter, setFilter] = useState<PinFilter>(EMPTY_FILTER)
  const [filterOpen, setFilterOpen] = useState(false)
  const [addOpen, setAddOpen] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)

  if (trips.isPending) return <p className="text-gray-500">불러오는 중…</p>
  if (!trip) {
    return (
      <Page>
        <h1 className="text-xl font-bold">장소</h1>
        <p className="text-gray-600">먼저 여행을 만들어 주세요.</p>
        <Link
          to="/"
          className="inline-flex min-h-11 items-center rounded-lg bg-teal-700 px-4 font-semibold text-white"
        >
          홈에서 여행 만들기
        </Link>
      </Page>
    )
  }

  const all = pins.data ?? []
  const shown = sortPins(filterPins(all, filter))
  const unresolved = unresolvedPins(all)
  const filterCount = filter.categories.length + filter.priorities.length
  const editing = all.find((p) => p.id === editId) ?? null
  const center =
    trip.center_lat !== null && trip.center_lng !== null
      ? { lat: trip.center_lat, lng: trip.center_lng }
      : DEFAULT_CENTER

  return (
    <>
      <MapLayout
        map={<PlacesMap pins={shown} center={center} selectedId={editId} onSelect={setEditId} />}
      >
        <div className="flex items-center gap-2">
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-xl font-bold">{trip.title}</h1>
            <p className="text-sm text-gray-500">
              장소 {all.length}곳{filterCount > 0 && ` · ${shown.length}곳 표시`}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setFilterOpen(true)}
            className="min-h-11 rounded-lg border border-gray-300 px-3 text-sm"
          >
            필터{filterCount > 0 && ` ${filterCount}`}
          </button>
          <button
            type="button"
            onClick={() => setAddOpen(true)}
            className="min-h-11 rounded-lg bg-teal-700 px-4 text-sm font-semibold text-white"
          >
            + 추가
          </button>
        </div>

        {unresolved.length > 0 && (
          <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
            Google 장소와 연결되지 않은 곳이 {unresolved.length}곳 있습니다. 눌러서 연결하세요.
          </p>
        )}

        <AiSuggestions tripId={trip.id} kind="place" />

        {pins.isError && <p className="text-sm text-red-700">{pins.error.message}</p>}
        {pins.isSuccess && all.length === 0 && (
          <p className="rounded-xl border border-dashed border-gray-300 bg-white p-4 text-gray-500">
            아직 장소가 없습니다. '+ 추가'로 검색하거나 Google 지도 링크를 붙여넣으세요.
          </p>
        )}

        {shown.length > 0 && (
          <ul className="divide-y divide-gray-100 overflow-hidden rounded-2xl border border-gray-200 bg-white">
            {shown.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  onClick={() => setEditId(p.id)}
                  className="flex min-h-14 w-full items-center gap-3 px-3 py-2 text-left"
                >
                  <span
                    aria-hidden
                    className="relative flex size-11 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-xl"
                  >
                    {CATEGORY_EMOJI[p.category] ?? '📍'}
                    <span
                      className="absolute -right-0.5 -bottom-0.5 size-3 rounded-full ring-2 ring-white"
                      style={{
                        background: isPriority(p.priority)
                          ? PRIORITY_COLORS[p.priority]
                          : '#6b7280',
                      }}
                    />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{p.label}</span>
                    <span className="block text-xs text-gray-500">
                      {categoryLabel(p.category)} · {formatMinutes(p.dwell_min)}
                      {p.meal && ` · ${MEAL_LABELS[p.meal] ?? p.meal}`}
                      {isPriority(p.priority) && ` · ${PRIORITY_LABELS[p.priority]}`}
                    </span>
                  </span>
                  {p.resolve_status !== 'ok' && (
                    <span className="shrink-0 rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
                      미연결
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </MapLayout>

      <BottomSheet open={filterOpen} title="필터" onClose={() => setFilterOpen(false)}>
        <div className="space-y-4">
          <div>
            <p className="mb-2 text-sm text-gray-600">우선순위</p>
            <div className="flex flex-wrap gap-2">
              {PRIORITIES.map((p) => (
                <Chip
                  key={p}
                  active={filter.priorities.includes(p)}
                  onClick={() => setFilter({ ...filter, priorities: toggle(filter.priorities, p) })}
                >
                  {PRIORITY_LABELS[p]}
                </Chip>
              ))}
            </div>
          </div>
          <div>
            <p className="mb-2 text-sm text-gray-600">카테고리</p>
            <div className="flex flex-wrap gap-2">
              {Object.keys(CATEGORY_LABELS).map((c) => (
                <Chip
                  key={c}
                  active={filter.categories.includes(c)}
                  onClick={() => setFilter({ ...filter, categories: toggle(filter.categories, c) })}
                >
                  {categoryLabel(c)}
                </Chip>
              ))}
            </div>
          </div>
          <button
            type="button"
            onClick={() => setFilter(EMPTY_FILTER)}
            className="min-h-11 w-full rounded-lg border border-gray-300 text-sm"
          >
            필터 지우기
          </button>
        </div>
      </BottomSheet>

      <AddPlaceSheet tripId={trip.id} open={addOpen} onClose={() => setAddOpen(false)} />
      <PinEditSheet tripId={trip.id} pin={editing} onClose={() => setEditId(null)} />
    </>
  )
}
