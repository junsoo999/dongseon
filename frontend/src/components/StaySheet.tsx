import { useState } from 'react'
import type { StayOut, TripOut } from '../api/client'
import { useCreateStay, useDeleteStay, useUpdateStay } from '../api/hooks'
import { newSessionToken } from '../lib/places'
import { CURRENCIES, parseAmount } from '../lib/stays'
import { BottomSheet } from './BottomSheet'
import { SearchPicker } from './SearchPicker'
import { PickPointMap } from './StaysMap'

type Where =
  | { kind: 'google'; googlePlaceId: string; token: string }
  | { kind: 'point'; lat: number; lng: number }

const inputClass = 'min-h-11 w-full rounded-lg border border-gray-300 px-3 text-base'

/** Create a stay (pick a place first) or edit one (`stay` given). */
export function StaySheet({
  trip,
  stay,
  open,
  onClose,
}: {
  trip: TripOut
  stay: StayOut | null
  open: boolean
  onClose: () => void
}) {
  return (
    <BottomSheet open={open} title={stay ? '숙소 편집' : '숙소 후보 추가'} onClose={onClose}>
      {open && <StayForm key={stay?.id ?? 'new'} trip={trip} stay={stay} onClose={onClose} />}
    </BottomSheet>
  )
}

function StayForm({
  trip,
  stay,
  onClose,
}: {
  trip: TripOut
  stay: StayOut | null
  onClose: () => void
}) {
  const [mode, setMode] = useState<'search' | 'map'>('search')
  const [token] = useState(newSessionToken)
  const [where, setWhere] = useState<Where | null>(null)
  const [label, setLabel] = useState(stay?.label ?? '')
  const [checkIn, setCheckIn] = useState(stay?.check_in ?? trip.start_date)
  const [checkOut, setCheckOut] = useState(stay?.check_out ?? trip.end_date)
  const [amount, setAmount] = useState(stay?.total_amount != null ? String(stay.total_amount) : '')
  const [currency, setCurrency] = useState(stay?.currency ?? 'JPY')
  const [url, setUrl] = useState(stay?.booking_url ?? '')
  const [booked, setBooked] = useState(stay?.status === 'booked')
  const create = useCreateStay(trip.id)
  const update = useUpdateStay(trip.id)
  const remove = useDeleteStay(trip.id)
  const center =
    trip.center_lat !== null && trip.center_lng !== null
      ? { lat: trip.center_lat, lng: trip.center_lng }
      : { lat: 35.681, lng: 139.767 }

  const amountValue = parseAmount(amount)
  const amountInvalid = amount.trim() !== '' && amountValue === null
  const datesInvalid = Boolean(checkIn && checkOut && checkOut <= checkIn)
  const error = create.error ?? update.error
  const pending = create.isPending || update.isPending

  if (!stay && !where) {
    return (
      <div className="space-y-3">
        <div className="grid grid-cols-2 rounded-lg bg-gray-100 p-1 text-sm">
          {(['search', 'map'] as const).map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={mode === m}
              onClick={() => setMode(m)}
              className={`min-h-10 rounded-md ${mode === m ? 'bg-white font-semibold shadow-sm' : 'text-gray-600'}`}
            >
              {m === 'search' ? '호텔 검색' : '지도에서 찍기'}
            </button>
          ))}
        </div>
        {mode === 'search' ? (
          <SearchPicker
            tripId={trip.id}
            sessionToken={token}
            placeholder="호텔 이름으로 검색"
            onPick={(s, query) => {
              setLabel(query)
              setWhere({ kind: 'google', googlePlaceId: s.google_place_id, token })
            }}
          />
        ) : (
          <MapPick center={center} onDone={(p) => setWhere({ kind: 'point', ...p })} />
        )}
      </div>
    )
  }

  const save = () => {
    const common = {
      label: label.trim(),
      check_in: checkIn || null,
      check_out: checkOut || null,
      total_amount: amountValue,
      currency,
      booking_url: url.trim() || null,
      status: booked ? ('booked' as const) : ('candidate' as const),
    }
    if (stay) {
      update.mutate({ id: stay.id, ...common }, { onSuccess: onClose })
      return
    }
    if (!where) return
    const location =
      where.kind === 'google'
        ? { google_place_id: where.googlePlaceId, session_token: where.token }
        : { user_lat: where.lat, user_lng: where.lng }
    create.mutate({ ...common, ...location }, { onSuccess: onClose })
  }

  return (
    <div className="space-y-3">
      {where?.kind === 'point' && (
        <p className="rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-600">
          지도에서 찍은 위치로 계산합니다.
        </p>
      )}
      <label className="block text-sm">
        <span className="mb-1 block text-gray-600">이름</span>
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          maxLength={100}
          className={inputClass}
          placeholder="예: 아사쿠사 에어비앤비"
        />
      </label>
      <div className="grid grid-cols-2 gap-3">
        <label className="block text-sm">
          <span className="mb-1 block text-gray-600">체크인</span>
          <input
            type="date"
            value={checkIn}
            onChange={(e) => setCheckIn(e.target.value)}
            className={inputClass}
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-gray-600">체크아웃</span>
          <input
            type="date"
            value={checkOut}
            min={checkIn}
            onChange={(e) => setCheckOut(e.target.value)}
            className={inputClass}
          />
        </label>
      </div>
      <div className="grid grid-cols-[1fr_6rem] gap-3">
        <label className="block text-sm">
          <span className="mb-1 block text-gray-600">총액 (세금·수수료 포함)</span>
          <input
            inputMode="numeric"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className={inputClass}
            placeholder="120000"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-gray-600">통화</span>
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className={inputClass}
          >
            {CURRENCIES.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
      </div>
      <label className="block text-sm">
        <span className="mb-1 block text-gray-600">예약 링크 (에어비앤비, 부킹닷컴 등)</span>
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          className={inputClass}
          placeholder="https://"
        />
      </label>
      <label className="flex min-h-11 items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={booked}
          onChange={(e) => setBooked(e.target.checked)}
          className="size-5"
        />
        예약 확정
      </label>
      {amountInvalid && <p className="text-sm text-red-700">총액은 숫자로 넣어 주세요.</p>}
      {datesInvalid && <p className="text-sm text-red-700">체크아웃이 체크인보다 늦어야 합니다.</p>}
      {error && <p className="text-sm text-red-700">{error.message}</p>}
      <button
        type="button"
        onClick={save}
        disabled={!label.trim() || amountInvalid || datesInvalid || pending}
        className="min-h-11 w-full rounded-lg bg-teal-700 font-semibold text-white disabled:opacity-50"
      >
        {pending ? '저장 중…' : '저장'}
      </button>
      {stay && (
        <button
          type="button"
          onClick={() => {
            if (window.confirm(`'${stay.label}'을(를) 지울까요?`))
              remove.mutate(stay.id, { onSuccess: onClose })
          }}
          className="min-h-11 w-full rounded-lg border border-red-200 text-sm text-red-700"
        >
          지우기
        </button>
      )}
    </div>
  )
}

function MapPick({
  center,
  onDone,
}: {
  center: { lat: number; lng: number }
  onDone: (p: { lat: number; lng: number }) => void
}) {
  const [point, setPoint] = useState<{ lat: number; lng: number } | null>(null)
  return (
    <div className="space-y-3">
      <p className="text-sm text-gray-600">
        숙소가 있는 대략적인 위치를 눌러 주세요. 정확한 주소가 없는 에어비앤비 등에 씁니다.
      </p>
      <PickPointMap center={center} value={point} onChange={setPoint} />
      <button
        type="button"
        disabled={!point}
        onClick={() => point && onDone(point)}
        className="min-h-11 w-full rounded-lg bg-teal-700 font-semibold text-white disabled:opacity-50"
      >
        이 위치로 계속
      </button>
    </div>
  )
}
