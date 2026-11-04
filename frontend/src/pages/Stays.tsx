import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import type { OriginOut, StayOut } from '../api/client'
import { usePins, useStays, useStayScore } from '../api/hooks'
import { AiSuggestions } from '../components/AiSuggestions'
import { StaySearchLinks } from '../components/SearchLinks'
import { StaySheet } from '../components/StaySheet'
import { StaysMap } from '../components/StaysMap'
import { formatKrw, formatMinutes, formatMoney } from '../lib/format'
import { rankColor } from '../lib/stays'
import { useCurrentTrip } from '../lib/trip'
import { MapLayout, Page } from '../components/MapLayout'

const AIRPORT_LABELS: Record<string, string> = { HND: '하네다', NRT: '나리타' }

function Chip({ children, tone = 'gray' }: { children: ReactNode; tone?: 'gray' | 'teal' }) {
  return (
    <span
      className={`rounded-md px-2 py-0.5 text-xs ${tone === 'teal' ? 'bg-teal-50 text-teal-800' : 'bg-slate-100 text-gray-700'}`}
    >
      {children}
    </span>
  )
}

function OriginRow({ o, total, onEdit }: { o: OriginOut; total: number; onEdit?: () => void }) {
  const body = (
    <>
      <span className="relative shrink-0">
        <span className="flex size-12 items-center justify-center rounded-2xl bg-slate-100 text-2xl">
          {o.emoji ?? (o.kind === 'stay' ? '🏠' : '📍')}
        </span>
        <span
          className="absolute -top-1.5 -left-1.5 flex h-6 min-w-6 items-center justify-center rounded-full px-1 text-xs font-bold text-white ring-2 ring-white"
          style={{ background: rankColor(o.rank, total) }}
        >
          {o.rank ?? '–'}
        </span>
      </span>
      <span className="min-w-0 flex-1 space-y-1">
        <span className="flex items-baseline justify-between gap-2">
          <span className="flex min-w-0 items-center gap-1.5">
            <span className="truncate text-[15px] font-semibold">{o.label}</span>
            {o.kind === 'stay' && (
              <span className="shrink-0 rounded bg-violet-100 px-1.5 text-xs text-violet-800">
                숙소
              </span>
            )}
          </span>
          {o.nightly_krw !== null && (
            <span className="shrink-0 text-sm font-semibold">
              {formatKrw(o.nightly_krw)}
              <span className="text-xs font-normal text-gray-500"> /박</span>
            </span>
          )}
        </span>
        {o.weighted_avg_min !== null ? (
          <span className="flex flex-wrap gap-1">
            <Chip tone="teal">평균 {formatMinutes(o.weighted_avg_min)}</Chip>
            <Chip>
              최장 {formatMinutes(o.max_min ?? 0)} · {o.farthest_label}
            </Chip>
            {Object.entries(o.airport_min).map(([code, m]) => (
              <Chip key={code}>
                ✈️ {AIRPORT_LABELS[code] ?? code} {formatMinutes(m)}
              </Chip>
            ))}
          </span>
        ) : (
          <span className="block text-xs text-gray-500">위치를 몰라 계산하지 못했습니다</span>
        )}
      </span>
    </>
  )
  const cls =
    'flex w-full items-center gap-3 rounded-2xl border border-gray-200 bg-white p-3 text-left'
  return onEdit ? (
    <button type="button" onClick={onEdit} className={`${cls} hover:border-teal-300`}>
      {body}
    </button>
  ) : (
    <div className={cls}>{body}</div>
  )
}

function StayDetail({ s }: { s: StayOut }) {
  return (
    <p className="px-3 pt-1 text-xs text-gray-500">
      {s.status === 'booked' ? '예약 확정' : '후보'}
      {s.check_in && ` · ${s.check_in} ~ ${s.check_out} (${s.nights}박)`}
      {s.total_amount !== null && ` · 총 ${formatMoney(s.total_amount, s.currency)}`}
      {s.booking_url && (
        <>
          {' · '}
          <a
            href={s.booking_url}
            target="_blank"
            rel="noreferrer"
            className="text-teal-700 underline"
          >
            예약 페이지
          </a>
        </>
      )}
    </p>
  )
}

export function Stays() {
  const { trip, trips } = useCurrentTrip()
  const tripId = trip?.id ?? null
  const score = useStayScore(tripId)
  const stays = useStays(tripId)
  const pins = usePins(tripId)
  const [sheet, setSheet] = useState<{ stay: StayOut | null } | null>(null)

  if (trips.isPending) return <p className="text-gray-500">불러오는 중…</p>
  if (!trip) {
    return (
      <Page>
        <h1 className="text-xl font-bold">숙소</h1>
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

  const origins = score.data?.origins ?? []
  const ranked = origins.filter((o) => o.rank !== null).length
  const stayById = new Map((stays.data ?? []).map((s) => [`stay:${s.id}`, s]))
  const center =
    trip.center_lat !== null && trip.center_lng !== null
      ? { lat: trip.center_lat, lng: trip.center_lng }
      : { lat: 35.681, lng: 139.767 }
  const openStay = (id: string) => {
    const s = stayById.get(id)
    if (s) setSheet({ stay: s })
  }

  return (
    <>
      <MapLayout
        map={
          <StaysMap origins={origins} pins={pins.data ?? []} center={center} onSelect={openStay} />
        }
      >
        <div className="flex items-center gap-2">
          <div className="min-w-0 flex-1">
            <h1 className="text-xl font-bold">어디에 묵을까</h1>
            <p className="text-sm text-gray-500">꼭·가고 싶음 장소까지의 이동시간 기준</p>
          </div>
          <button
            type="button"
            onClick={() => setSheet({ stay: null })}
            className="min-h-11 rounded-lg bg-teal-700 px-4 text-sm font-semibold text-white"
          >
            + 숙소 후보
          </button>
        </div>

        {score.isError && <p className="text-sm text-red-700">{score.error.message}</p>}
        {score.data && score.data.targets === 0 && (
          <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
            '꼭'이나 '가고 싶음'으로 표시한 장소가 없어 순위를 매길 수 없습니다.{' '}
            <Link to="/places" className="underline">
              장소에서 우선순위를 정해 주세요
            </Link>
            .
          </p>
        )}

        {origins.length > 0 && (
          <ul className="space-y-2">
            {origins.map((o) => {
              const s = stayById.get(o.id)
              return (
                <li key={o.id}>
                  <OriginRow
                    o={o}
                    total={ranked}
                    onEdit={s ? () => setSheet({ stay: s }) : undefined}
                  />
                  {s && <StayDetail s={s} />}
                </li>
              )
            })}
          </ul>
        )}

        <StaySearchLinks tripId={trip.id} />
        <AiSuggestions tripId={trip.id} kind="stay" />

        {score.data && (
          <div className="space-y-1 rounded-lg bg-gray-50 p-3 text-xs text-gray-600">
            <p>
              <strong className="font-semibold">근사</strong>: Google이 일본 대중교통 경로를
              제공하지 않아 직선거리로 추정합니다. 동네끼리 비교하는 용도이고, 실제 시간은 Google
              지도 앱에서 확인하세요.
            </p>
            <p>
              가중치: 꼭 {score.data.weights.must} · 가고 싶음 {score.data.weights.want} · 장소{' '}
              {score.data.targets}곳
              {score.data.targets_without_coords > 0 &&
                ` (위치 없는 ${score.data.targets_without_coords}곳 제외)`}
            </p>
            {Object.entries(score.data.airport_notes).map(([code, note]) => (
              <p key={code}>
                {AIRPORT_LABELS[code] ?? code}: {note} 포함
              </p>
            ))}
            {score.data.approx_source_url && (
              <p>
                철도 평균 속도 출처:{' '}
                <a
                  href={score.data.approx_source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="underline"
                >
                  링크
                </a>{' '}
                ({score.data.approx_as_of} 기준)
              </p>
            )}
            {score.data.fx.map((f) => (
              <p key={f.base}>
                1박 가격 환산: 1 {f.base} = {f.rate} {f.quote} ({f.source}, {f.date} 기준)
              </p>
            ))}
          </div>
        )}
      </MapLayout>

      {sheet && <StaySheet trip={trip} stay={sheet.stay} open onClose={() => setSheet(null)} />}
    </>
  )
}
