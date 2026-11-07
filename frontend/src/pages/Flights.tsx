import { useState } from 'react'
import { Link } from 'react-router'
import type { FlightDraft, FlightOut } from '../api/client'
import { useFlights } from '../api/hooks'
import { BookingPasteSheet } from '../components/BookingPaste'
import { FlightSheet } from '../components/FlightSheet'
import { LegLine } from '../components/LegLine'
import { carrierCode } from '../lib/airlines'
import type { LegSegment } from '../lib/legs'
import { BTN } from '../lib/theme'
import { LiveFares } from '../components/LivePrices'
import { FlightSearchLinks } from '../components/SearchLinks'
import { formatKrw, formatLocal, formatMoney, formatSpan, minutesBetween } from '../lib/format'
import { useCurrentTrip } from '../lib/trip'
import { Page } from '../components/MapLayout'

const REF_LABEL = {
  booked_stay: '확정 숙소',
  top_area: '1위 동네',
  first_area: '기본 동네',
  none: '',
} as const

function Timeline({ flights }: { flights: FlightOut[] }) {
  const rows = flights.filter((f) => f.evaluation)
  if (rows.length === 0) return null
  const evs = rows.map((f) => f.evaluation!)
  const start = `${evs.map((e) => e.arrival_local.slice(0, 10)).sort()[0]}T00:00`
  const lastDay = evs
    .map((e) => e.departure_local.slice(0, 10))
    .sort()
    .at(-1)!
  const total = minutesBetween(start, `${lastDay}T23:59`) + 1
  const pct = (iso: string) =>
    `${Math.max(0, Math.min(100, (minutesBetween(start, iso) / total) * 100))}%`
  const days = Math.round(total / 1440)
  const firstDate = new Date(`${start.slice(0, 10)}T00:00:00Z`)
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3">
      <h2 className="mb-2 text-sm font-semibold">현지에서 쓰는 시간</h2>
      <div className="relative mb-1 h-4 text-[10px] text-gray-500">
        {Array.from({ length: days }, (_, i) => {
          const d = new Date(firstDate.getTime() + i * 86_400_000)
          return (
            <span key={i} className="absolute" style={{ left: `${(i / days) * 100}%` }}>
              {d.getUTCMonth() + 1}/{d.getUTCDate()}
            </span>
          )
        })}
      </div>
      <div className="space-y-2">
        {rows.map((f) => {
          const e = f.evaluation!
          return (
            <div key={f.id}>
              <p className="mb-0.5 truncate text-xs text-gray-700">{f.label}</p>
              <div className="relative h-4 rounded bg-gray-100">
                {Array.from({ length: days - 1 }, (_, i) => (
                  <span
                    key={i}
                    className="absolute top-0 h-full w-px bg-white"
                    style={{ left: `${((i + 1) / days) * 100}%` }}
                  />
                ))}
                <span
                  className="absolute top-1 h-2 rounded bg-gray-400"
                  style={{
                    left: pct(e.arrival_local),
                    right: `calc(100% - ${pct(e.departure_local)})`,
                  }}
                />
                {e.ready_local && e.leave_by_local && (
                  <span
                    className="absolute h-full rounded bg-teal-600"
                    style={{
                      left: pct(e.ready_local),
                      right: `calc(100% - ${pct(e.leave_by_local)})`,
                    }}
                  />
                )}
              </div>
            </div>
          )
        })}
      </div>
      <p className="mt-2 text-xs text-gray-500">
        초록: 숙소에 도착한 뒤부터 공항으로 떠나기 전까지 · 회색: 도착~출발
      </p>
    </div>
  )
}

function legSegments(f: FlightOut, direction: 'out' | 'back'): LegSegment[] {
  return f.legs
    .filter((l) => l.direction === direction)
    .map((l) => ({
      flight: l.flight_no,
      carrierCode: carrierCode(l.flight_no),
      carrier: l.carrier,
      depAirport: l.dep_airport,
      depLocal: l.dep_local,
      arrAirport: l.arr_airport,
      arrLocal: l.arr_local,
      durationMin: l.duration_min,
    }))
}

function FlightCard({ f, best, onEdit }: { f: FlightOut; best: boolean; onEdit: () => void }) {
  const e = f.evaluation
  const krw = e?.total_krw ?? (f.currency === 'KRW' ? f.total_amount : null)
  return (
    <button
      type="button"
      onClick={onEdit}
      className={`block w-full space-y-3 rounded-2xl border bg-white p-4 text-left shadow-sm hover:border-teal-300 ${f.status === 'booked' ? 'border-teal-500 ring-1 ring-teal-500' : 'border-gray-200'}`}
    >
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-1.5 font-semibold">
            {f.label}
            {f.status === 'booked' && (
              <span className="rounded-md bg-teal-600 px-1.5 py-0.5 text-xs font-semibold text-white">
                확정
              </span>
            )}
            {best && (
              <span className="rounded-md bg-amber-500 px-1.5 py-0.5 text-xs font-semibold text-white">
                현지 시간 최다
              </span>
            )}
          </p>
          {f.baggage_note && <p className="text-xs text-gray-500">🧳 {f.baggage_note}</p>}
        </div>
        {f.total_amount !== null && (
          <p className="shrink-0 text-right text-lg leading-tight font-bold">
            {krw !== null ? formatKrw(krw) : formatMoney(f.total_amount, f.currency)}
            {f.currency !== 'KRW' && (
              <span className="block text-xs font-normal text-gray-500">
                {formatMoney(f.total_amount, f.currency)}
              </span>
            )}
          </p>
        )}
      </div>
      <LegLine label="가는 편" segs={legSegments(f, 'out')} />
      <LegLine label="오는 편" segs={legSegments(f, 'back')} />
      {e && (
        <div className="space-y-0.5 rounded-xl bg-slate-50 p-3 text-sm">
          {e.usable_min !== null ? (
            <p>
              현지 <strong>{formatSpan(e.usable_min)}</strong>
              {e.krw_per_usable_hour !== null && (
                <span className="text-gray-600"> · 1시간당 {formatKrw(e.krw_per_usable_hour)}</span>
              )}
            </p>
          ) : (
            <p className="text-gray-600">현지 가용 시간 계산 불가</p>
          )}
          {e.ready_local && e.leave_by_local && (
            <p className="text-xs text-gray-600">
              {formatLocal(e.ready_local)}부터 {formatLocal(e.leave_by_local)}까지 (
              {REF_LABEL[e.reference_kind]} {e.reference_label} 기준)
            </p>
          )}
          {e.access_in_min !== null && (
            <p className="text-xs text-gray-500">
              입국 {e.immigration_buffer_min}분 + 공항→숙소 {e.access_in_min}분(근사) · 숙소→공항{' '}
              {e.access_out_min}분(근사) + 공항 {e.departure_buffer_min}분 전 도착
            </p>
          )}
          {e.warnings.map((w) => (
            <p key={w} className="text-xs text-amber-700">
              {w}
            </p>
          ))}
        </div>
      )}
      {f.problems.map((pr) => (
        <p key={pr} className="text-xs text-red-700">
          {pr}
        </p>
      ))}
    </button>
  )
}

export function Flights() {
  const { trip, trips } = useCurrentTrip()
  const flights = useFlights(trip?.id ?? null)
  const [sheet, setSheet] = useState<{ flight: FlightOut | null; draft?: FlightDraft } | null>(null)
  const [pasting, setPasting] = useState(false)

  if (trips.isPending) return <p className="text-gray-500">불러오는 중…</p>
  if (!trip) {
    return (
      <Page>
        <h1 className="text-xl font-bold">항공</h1>
        <Link
          to="/"
          className="inline-flex min-h-11 items-center rounded-lg bg-teal-700 px-4 font-semibold text-white"
        >
          홈에서 여행 만들기
        </Link>
      </Page>
    )
  }

  const list = flights.data ?? []
  const usable = list.map((f) => f.evaluation?.usable_min ?? -1)
  const bestId =
    list.length > 1 && Math.max(...usable) > 0 ? list[usable.indexOf(Math.max(...usable))].id : null
  const noReference = list.some((f) => f.evaluation?.reference_kind === 'none')

  return (
    <Page>
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-bold">항공 후보</h1>
          <p className="text-sm text-gray-500">
            검색은 Google 항공권 등에서 하고, 후보를 넣어 비교하세요
          </p>
        </div>
        <button
          type="button"
          onClick={() => setSheet({ flight: null })}
          className={`${BTN.primary} shrink-0`}
        >
          + 항공 후보
        </button>
      </div>

      <button type="button" onClick={() => setPasting(true)} className={`${BTN.soft} w-full`}>
        📋 예약 메일로 입력
      </button>
      <LiveFares tripId={trip.id} />
      <FlightSearchLinks tripId={trip.id} />
      {flights.isError && <p className="text-sm text-red-700">{flights.error.message}</p>}
      {noReference && (
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
          공항↔숙소 시간을 계산하려면{' '}
          <Link to="/places" className="underline">
            '꼭' 장소
          </Link>
          를 넣어 동네 순위를 만들거나{' '}
          <Link to="/stays" className="underline">
            숙소를 확정
          </Link>
          해 주세요.
        </p>
      )}
      {flights.isSuccess && list.length === 0 && (
        <p className="rounded-xl border border-dashed border-gray-300 bg-white p-4 text-gray-500">
          아직 항공 후보가 없습니다. '+ 항공 후보'로 편명과 시각을 넣어 보세요.
        </p>
      )}

      <Timeline flights={list} />
      <div className="space-y-3">
        {list.map((f) => (
          <FlightCard
            key={f.id}
            f={f}
            best={f.id === bestId}
            onEdit={() => setSheet({ flight: f })}
          />
        ))}
      </div>

      {sheet && (
        <FlightSheet
          trip={trip}
          flight={sheet.flight}
          draft={sheet.draft}
          onClose={() => setSheet(null)}
        />
      )}
      {pasting && (
        <BookingPasteSheet
          tripId={trip.id}
          onClose={() => setPasting(false)}
          onResult={(r) => {
            setPasting(false)
            if (r.flight) setSheet({ flight: null, draft: r.flight })
          }}
        />
      )}
    </Page>
  )
}
