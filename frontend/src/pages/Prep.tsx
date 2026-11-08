import { useState } from 'react'
import { Link } from 'react-router'
import type { BookingsOut, ChecklistItemOut, OfflineOut } from '../api/client'
import {
  useAddChecklistItem,
  useBookings,
  useChecklist,
  useDeleteChecklistItem,
  usePatchChecklistItem,
  useSeedChecklist,
} from '../api/hooks'
import { Page } from '../components/MapLayout'
import { dayLabel } from '../lib/airlines'
import { formatLocal, formatMoney } from '../lib/format'
import { isUnreachable, savedAtLabel } from '../lib/offline'
import { BTN } from '../lib/theme'
import { useCurrentTrip } from '../lib/trip'
import { useOffline } from '../lib/useOffline'

const card = 'rounded-2xl border border-gray-200 bg-white p-4'

function groupBySection(items: ChecklistItemOut[]): [string, ChecklistItemOut[]][] {
  const out = new Map<string, ChecklistItemOut[]>()
  for (const i of items) out.set(i.section, [...(out.get(i.section) ?? []), i])
  return [...out.entries()]
}

function ChecklistSection({
  tripId,
  items,
  asOf,
  readOnly,
}: {
  tripId: number
  items: ChecklistItemOut[]
  asOf: string | null
  readOnly: boolean
}) {
  const seed = useSeedChecklist(tripId)
  const add = useAddChecklistItem(tripId)
  const patch = usePatchChecklistItem(tripId)
  const remove = useDeleteChecklistItem(tripId)
  const [text, setText] = useState('')
  const done = items.filter((i) => i.done).length

  const submit = () => {
    if (!text.trim()) return
    add.mutate({ text: text.trim(), section: '기타' }, { onSuccess: () => setText('') })
  }

  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-lg font-bold">체크리스트</h2>
        {items.length > 0 && (
          <span className="text-sm text-gray-500">
            {done}/{items.length} 완료
          </span>
        )}
      </div>
      {items.length === 0 && !readOnly && (
        <div className={`${card} space-y-2 text-sm text-gray-600`}>
          <p>여권, 입국 등록, 통신, 출발 전 dongseon 점검 같은 기본 항목으로 시작할 수 있습니다.</p>
          <button
            className={BTN.primary}
            onClick={() => seed.mutate(undefined)}
            disabled={seed.isPending}
          >
            기본 항목 채우기
          </button>
        </div>
      )}
      {groupBySection(items).map(([section, rows]) => (
        <div key={section} className="space-y-1">
          <p className="text-xs font-semibold text-gray-500">{section}</p>
          <ul className="divide-y divide-gray-100 rounded-2xl border border-gray-200 bg-white">
            {rows.map((i) => (
              <li key={i.id} className="flex items-center gap-2 px-3">
                <label className="flex min-h-11 flex-1 items-center gap-3 py-2">
                  <input
                    type="checkbox"
                    checked={i.done}
                    disabled={readOnly}
                    onChange={(e) => patch.mutate({ id: i.id, done: e.target.checked })}
                    className="size-5 shrink-0 accent-teal-700"
                  />
                  <span className={`text-sm ${i.done ? 'text-gray-400 line-through' : ''}`}>
                    {i.text}
                  </span>
                </label>
                {i.url && (
                  <a
                    href={i.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex min-h-11 shrink-0 items-center px-1 text-xs font-medium text-teal-700"
                  >
                    공식 안내
                  </a>
                )}
                {!readOnly && (
                  <button
                    aria-label={`${i.text} 삭제`}
                    onClick={() => remove.mutate(i.id)}
                    className="flex size-11 shrink-0 items-center justify-center text-gray-400 hover:text-red-600"
                  >
                    ✕
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
      {!readOnly && (
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            submit()
          }}
        >
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="항목 추가"
            aria-label="체크리스트 항목"
            maxLength={200}
            className="min-h-11 min-w-0 flex-1 rounded-xl border border-gray-300 px-3 text-base"
          />
          <button className={BTN.soft} disabled={!text.trim() || add.isPending}>
            추가
          </button>
        </form>
      )}
      {asOf && items.some((i) => i.url) && (
        <p className="text-[11px] text-gray-400">
          기본 항목 {asOf} 기준. 입국 절차 같은 내용은 공식 안내에서 다시 확인하세요.
        </p>
      )}
    </section>
  )
}

function money(amount: number | null, currency: string): string | null {
  return amount === null ? null : formatMoney(amount, currency)
}

function BookingsSection({ data }: { data: BookingsOut }) {
  const empty = !data.flights.length && !data.stays.length && !data.reservations.length
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-bold">예약 정보</h2>
      {empty && (
        <p className={`${card} text-sm text-gray-600`}>
          확정한 항공·숙소나 예약 시각을 넣은 장소가 없습니다.{' '}
          <Link to="/flights" className="font-semibold text-teal-700 underline">
            항공
          </Link>
          {' · '}
          <Link to="/stays" className="font-semibold text-teal-700 underline">
            숙소
          </Link>
          에서 확정하면 여기에 모입니다.
        </p>
      )}
      {data.flights.map((f) => (
        <div key={`f${f.id}`} className={`${card} space-y-1 text-sm`}>
          <p className="font-semibold">✈️ {f.label}</p>
          {f.legs.map((l, n) => (
            <p key={n} className="text-gray-700">
              {l.direction === 'out' ? '가는 편' : '오는 편'} {l.flight_no ?? l.carrier ?? ''} ·{' '}
              {l.dep_airport} {formatLocal(l.dep_local)} → {l.arr_airport}{' '}
              {formatLocal(l.arr_local)}
            </p>
          ))}
          <BookingMeta
            price={money(f.total_amount, f.currency)}
            note={[f.baggage_note, f.note].filter(Boolean).join(' / ')}
            url={f.booking_url}
          />
        </div>
      ))}
      {data.stays.map((s) => (
        <div key={`s${s.id}`} className={`${card} space-y-1 text-sm`}>
          <p className="font-semibold">🏨 {s.label}</p>
          {s.check_in && s.check_out && (
            <p className="text-gray-700">
              체크인 {dayLabel(`${s.check_in}T00:00`)} · 체크아웃 {dayLabel(`${s.check_out}T00:00`)}
            </p>
          )}
          <BookingMeta
            price={money(s.total_amount, s.currency)}
            note={s.note}
            url={s.booking_url}
          />
        </div>
      ))}
      {data.reservations.length > 0 && (
        <div className={`${card} space-y-1 text-sm`}>
          <p className="font-semibold">🍽️ 예약한 시각</p>
          {data.reservations.map((r) => (
            <p key={r.pin_id} className="text-gray-700">
              {formatLocal(r.start_local)}
              {r.end_local ? `~${r.end_local.slice(11, 16)}` : ''} · {r.label}
              {r.note ? ` · ${r.note}` : ''}
            </p>
          ))}
        </div>
      )}
    </section>
  )
}

function BookingMeta({
  price,
  note,
  url,
}: {
  price: string | null
  note: string | null | undefined
  url: string | null
}) {
  return (
    <>
      {(price || note) && (
        <p className="text-xs text-gray-500">{[price, note].filter(Boolean).join(' · ')}</p>
      )}
      {url && (
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="text-xs font-medium text-teal-700"
        >
          예약 페이지 열기
        </a>
      )}
    </>
  )
}

function ExportSection({ bundle }: { bundle: OfflineOut }) {
  const id = bundle.itinerary_id
  if (!id) {
    return (
      <section className="space-y-3">
        <h2 className="text-lg font-bold">출발 전 내보내기</h2>
        <p className={`${card} text-sm text-gray-600`}>
          일정이 생기면 내보낼 수 있습니다.{' '}
          <Link to="/itinerary" className="font-semibold text-teal-700 underline">
            일정에서 초안 만들기
          </Link>
        </p>
      </section>
    )
  }
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-bold">출발 전 내보내기</h2>
      <div className={`${card} space-y-3 text-sm`}>
        <p className="text-gray-600">
          지금 일정(v{bundle.version}) 기준입니다. 일정을 바꾸면 다시 내보내세요. 파일에는
          영업시간·좌표를 넣지 않습니다.
        </p>
        <a href={`/api/itineraries/${id}/mymaps.zip`} className={`${BTN.primary} w-full`}>
          Google 내 지도용 CSV (날짜별 zip)
        </a>
        <p className="text-xs text-gray-500">
          google.com/maps/d에서 새 지도 → 레이어마다 가져오기 → 위치 열은 '위치', 제목은 '이름'.
          현지 이름을 넣은 장소가 더 정확히 찾아집니다.
        </p>
        <div className="grid grid-cols-2 gap-2">
          <a href={`/api/itineraries/${id}/export.ics`} className={BTN.secondary}>
            캘린더 (ICS)
          </a>
          <a
            href={`/api/itineraries/${id}/print`}
            target="_blank"
            rel="noreferrer"
            className={BTN.secondary}
          >
            인쇄용 보기
          </a>
        </div>
      </div>
      <div className={`${card} space-y-2 text-sm`}>
        <p className="font-semibold">날짜별 Google 지도 경로</p>
        {bundle.days.map((d) => (
          <p key={d.date} className="flex flex-wrap items-center gap-x-3">
            <span className="w-16 shrink-0 text-gray-600">{dayLabel(`${d.date}T00:00`)}</span>
            {d.route_urls.length === 0 && <span className="text-gray-400">일정 없음</span>}
            {d.route_urls.map((u, n) => (
              <a
                key={u}
                href={u}
                target="_blank"
                rel="noreferrer"
                className="flex min-h-11 items-center font-medium text-teal-700"
              >
                경로{d.route_urls.length > 1 ? ` ${n + 1}` : ''}
              </a>
            ))}
          </p>
        ))}
        <p className="text-[11px] text-gray-400">
          한 링크에 장소 5곳까지 넣고, 더 많으면 나눠서 엽니다.
        </p>
      </div>
    </section>
  )
}

export function Prep() {
  const { trip, trips } = useCurrentTrip()
  const tripId = trip?.id ?? null
  const checklist = useChecklist(tripId)
  const bookings = useBookings(tripId)
  const { tripsDown, bundle, live } = useOffline()

  const unreachable =
    tripsDown ||
    (checklist.isError && isUnreachable(checklist.error)) ||
    (bookings.isError && isUnreachable(bookings.error))

  if (unreachable) {
    if (!bundle)
      return (
        <Page>
          <p className="text-sm text-gray-600">연결이 없고 저장된 준비물도 없습니다.</p>
        </Page>
      )
    return (
      <Page>
        <div>
          <h1 className="text-xl font-bold">준비 · 저장된 내용</h1>
          <p className="text-sm text-gray-500">
            {bundle.trip.title} · {savedAtLabel(bundle.generated_at)} 저장 · 연결되면 다시 고칠 수
            있습니다
          </p>
        </div>
        <ChecklistSection tripId={bundle.trip.id} items={bundle.checklist} asOf={null} readOnly />
        <BookingsSection data={bundle.bookings} />
      </Page>
    )
  }

  if (trips.isPending) return <p className="text-gray-500">불러오는 중…</p>
  if (!trip) {
    return (
      <Page>
        <h1 className="text-xl font-bold">준비</h1>
        <Link to="/" className={BTN.primary}>
          홈에서 여행 만들기
        </Link>
      </Page>
    )
  }
  return (
    <Page>
      <div>
        <h1 className="text-xl font-bold">준비</h1>
        <p className="text-sm text-gray-500">
          {trip.title}
          {live &&
            bundle &&
            ` · 이 휴대폰에 ${savedAtLabel(bundle.generated_at)} 저장됨 (오프라인용)`}
        </p>
      </div>
      {checklist.isError && <p className="text-sm text-red-700">{checklist.error.message}</p>}
      {checklist.data && (
        <ChecklistSection
          tripId={trip.id}
          items={checklist.data.items}
          asOf={checklist.data.template_as_of}
          readOnly={false}
        />
      )}
      {bookings.data && <BookingsSection data={bookings.data} />}
      {bundle && bundle.trip.id === trip.id && <ExportSection bundle={bundle} />}
    </Page>
  )
}
