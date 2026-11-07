import { useState } from 'react'
import type { FlightDraft, FlightIn, FlightOut, LegIn, TripOut } from '../api/client'
import { useAirports, useDeleteFlight, useSaveFlight } from '../api/hooks'
import { CURRENCIES, parseAmount } from '../lib/stays'
import { BottomSheet } from './BottomSheet'

type Direction = 'out' | 'back'
interface LegDraft {
  direction: Direction
  flight_no: string
  dep_airport: string
  dep_local: string
  arr_airport: string
  arr_local: string
}

const inputClass = 'min-h-11 w-full min-w-0 rounded-lg border border-gray-300 px-2 text-base'

function blankLeg(direction: Direction, trip: TripOut): LegDraft {
  return direction === 'out'
    ? {
        direction,
        flight_no: '',
        dep_airport: 'ICN',
        dep_local: `${trip.start_date}T09:00`,
        arr_airport: 'NRT',
        arr_local: `${trip.start_date}T11:30`,
      }
    : {
        direction,
        flight_no: '',
        dep_airport: 'NRT',
        dep_local: `${trip.end_date}T18:00`,
        arr_airport: 'ICN',
        arr_local: `${trip.end_date}T20:30`,
      }
}

function fromFlight(f: FlightOut): LegDraft[] {
  return f.legs.map((l) => ({
    direction: l.direction === 'back' ? 'back' : 'out',
    flight_no: l.flight_no ?? '',
    dep_airport: l.dep_airport,
    dep_local: l.dep_local,
    arr_airport: l.arr_airport,
    arr_local: l.arr_local,
  }))
}

function fromDraft(d: FlightDraft): LegDraft[] {
  return d.legs.map((l) => ({
    direction: l.direction,
    flight_no: l.flight_no ?? '',
    dep_airport: l.dep_airport,
    dep_local: l.dep_local.slice(0, 16),
    arr_airport: l.arr_airport,
    arr_local: l.arr_local.slice(0, 16),
  }))
}

/** Add or edit a flight; ``draft`` pre-fills a new booked flight from a pasted booking email. */
export function FlightSheet({
  trip,
  flight,
  draft,
  onClose,
}: {
  trip: TripOut
  flight: FlightOut | null
  draft?: FlightDraft
  onClose: () => void
}) {
  const airports = useAirports()
  const save = useSaveFlight(trip.id)
  const remove = useDeleteFlight(trip.id)
  const [label, setLabel] = useState(flight?.label ?? draft?.label ?? '')
  const [amount, setAmount] = useState(
    flight?.total_amount != null
      ? String(flight.total_amount)
      : draft?.total_amount != null
        ? String(draft.total_amount)
        : '',
  )
  const [currency, setCurrency] = useState(flight?.currency ?? draft?.currency ?? 'KRW')
  const [baggage, setBaggage] = useState(flight?.baggage_note ?? draft?.baggage_note ?? '')
  const [url, setUrl] = useState(flight?.booking_url ?? '')
  const [booked, setBooked] = useState(flight ? flight.status === 'booked' : !!draft)
  const [legs, setLegs] = useState<LegDraft[]>(() =>
    flight
      ? fromFlight(flight)
      : draft
        ? fromDraft(draft)
        : [blankLeg('out', trip), blankLeg('back', trip)],
  )
  const amountValue = parseAmount(amount)
  const amountInvalid = amount.trim() !== '' && amountValue === null
  const legsInvalid = legs.length === 0 || legs.some((l) => !l.dep_local || !l.arr_local)

  const setLeg = (i: number, patch: Partial<LegDraft>) =>
    setLegs(legs.map((l, j) => (j === i ? { ...l, ...patch } : l)))

  const submit = () => {
    const body: FlightIn = {
      label: label.trim(),
      total_amount: amountValue,
      currency,
      baggage_note: baggage.trim() || null,
      booking_url: url.trim() || null,
      note: null,
      status: booked ? 'booked' : 'candidate',
      legs: legs.map((l): LegIn => ({
        direction: l.direction,
        carrier: null,
        flight_no: l.flight_no.trim() || null,
        dep_airport: l.dep_airport,
        dep_local: l.dep_local,
        arr_airport: l.arr_airport,
        arr_local: l.arr_local,
      })),
    }
    save.mutate({ id: flight?.id ?? null, body }, { onSuccess: onClose })
  }

  const airportOptions = (airports.data ?? []).map((a) => (
    <option key={a.code} value={a.code}>
      {a.code} {a.name}
    </option>
  ))

  return (
    <BottomSheet open title={flight ? '항공 후보 편집' : '항공 후보 추가'} onClose={onClose}>
      <div className="space-y-3">
        <label className="block text-sm">
          <span className="mb-1 block text-gray-600">이름</span>
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            maxLength={100}
            className={inputClass}
            placeholder="예: 대한항공 아침 출발"
          />
        </label>

        {legs.map((l, i) => (
          <fieldset key={i} className="min-w-0 space-y-2 rounded-lg border border-gray-200 p-3">
            <legend className="px-1 text-sm font-medium">
              {l.direction === 'out' ? '가는 편' : '오는 편'}{' '}
              {legs.filter((x, j) => x.direction === l.direction && j <= i).length}
            </legend>
            <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-2">
              <input
                value={l.flight_no}
                onChange={(e) => setLeg(i, { flight_no: e.target.value.toUpperCase() })}
                placeholder="편명 (예: KE703)"
                className={inputClass}
                aria-label="편명"
              />
              <button
                type="button"
                onClick={() => setLegs(legs.filter((_, j) => j !== i))}
                className="min-h-11 rounded-lg px-3 text-sm text-gray-500"
              >
                구간 삭제
              </button>
            </div>
            <div className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-2">
              <select
                aria-label="출발 공항"
                value={l.dep_airport}
                onChange={(e) => setLeg(i, { dep_airport: e.target.value })}
                className={inputClass}
              >
                {airportOptions}
              </select>
              <input
                aria-label="출발 (현지 시각)"
                type="datetime-local"
                value={l.dep_local}
                onChange={(e) => setLeg(i, { dep_local: e.target.value })}
                className={inputClass}
              />
              <select
                aria-label="도착 공항"
                value={l.arr_airport}
                onChange={(e) => setLeg(i, { arr_airport: e.target.value })}
                className={inputClass}
              >
                {airportOptions}
              </select>
              <input
                aria-label="도착 (현지 시각)"
                type="datetime-local"
                value={l.arr_local}
                onChange={(e) => setLeg(i, { arr_local: e.target.value })}
                className={inputClass}
              />
            </div>
          </fieldset>
        ))}
        <p className="text-xs text-gray-500">시각은 각 공항의 현지 시각으로 넣으세요.</p>
        <div className="grid grid-cols-2 gap-2">
          {(['out', 'back'] as const).map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => {
                const last = [...legs].reverse().find((l) => l.direction === d)
                const next = last
                  ? {
                      ...blankLeg(d, trip),
                      dep_airport: last.arr_airport,
                      dep_local: last.arr_local,
                      arr_local: last.arr_local,
                    }
                  : blankLeg(d, trip)
                setLegs([...legs, next])
              }}
              className="min-h-11 rounded-lg border border-gray-300 text-sm"
            >
              + {d === 'out' ? '가는 편' : '오는 편'} 구간
            </button>
          ))}
        </div>

        <div className="grid grid-cols-[1fr_6rem] gap-3">
          <label className="block text-sm">
            <span className="mb-1 block text-gray-600">총액 (일행 전체)</span>
            <input
              inputMode="numeric"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className={inputClass}
              placeholder="700000"
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
          <span className="mb-1 block text-gray-600">수하물</span>
          <input
            value={baggage}
            onChange={(e) => setBaggage(e.target.value)}
            maxLength={200}
            className={inputClass}
            placeholder="예: 위탁 23kg 1개 포함"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-gray-600">예약·검색 링크</span>
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
          예약 확정 (확정은 한 후보만)
        </label>
        {amountInvalid && <p className="text-sm text-red-700">총액은 숫자로 넣어 주세요.</p>}
        {save.error && <p className="text-sm text-red-700">{save.error.message}</p>}
        <button
          type="button"
          onClick={submit}
          disabled={!label.trim() || amountInvalid || legsInvalid || save.isPending}
          className="min-h-11 w-full rounded-lg bg-teal-700 font-semibold text-white disabled:opacity-50"
        >
          {save.isPending ? '저장 중…' : '저장'}
        </button>
        {flight && (
          <button
            type="button"
            onClick={() => {
              if (window.confirm(`'${flight.label}'을(를) 지울까요?`))
                remove.mutate(flight.id, { onSuccess: onClose })
            }}
            className="min-h-11 w-full rounded-lg border border-red-200 text-sm text-red-700"
          >
            지우기
          </button>
        )}
      </div>
    </BottomSheet>
  )
}
