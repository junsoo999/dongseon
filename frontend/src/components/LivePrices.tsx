import { useMemo, useState } from 'react'
import type { FareOut, VacancyOut } from '../api/client'
import { useAddOffer, useFarePrefs, useFares, useHotels, useJob } from '../api/hooks'
import { prefsChips } from '../lib/farePrefs'
import { formatKrw, formatMoney, formatSpan } from '../lib/format'
import type { LegSegment } from '../lib/legs'
import { BADGE, BTN, PANEL } from '../lib/theme'
import { BrandIcon } from './BrandIcon'
import { FarePrefsSheet } from './FarePrefsSheet'
import { JobButton } from './JobButton'
import { LegLine } from './LegLine'
import { LoadingBlock } from './Loading'

function fetchedLabel(iso: string | null | undefined): string {
  if (!iso) return '아직 가져오지 않았습니다'
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')} 기준`
}

function segments(f: FareOut, direction: 'out' | 'back'): LegSegment[] {
  return f.legs
    .filter((l) => l.direction === direction)
    .map((l) => ({
      flight: l.flight,
      carrierCode: l.carrier_code,
      carrier: l.carrier ?? null,
      depAirport: l.dep_airport,
      depLocal: l.dep_local,
      arrAirport: l.arr_airport,
      arrLocal: l.arr_local,
      durationMin: l.duration_min,
    }))
}

function FareRow({ f, tripId }: { f: FareOut; tripId: number }) {
  const add = useAddOffer(tripId, 'fares')
  return (
    <li className="space-y-3 rounded-2xl border border-gray-200 bg-white p-3.5 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          {f.best_value && (
            <span className="rounded-md bg-sky-600 px-1.5 py-0.5 text-xs font-semibold text-white">
              가성비 1위
            </span>
          )}
          {f.cheapest && (
            <span className="rounded-md bg-amber-500 px-1.5 py-0.5 text-xs font-semibold text-white">
              최저가
            </span>
          )}
        </div>
        <p className="text-right text-lg leading-tight font-bold">
          {f.total_krw !== null ? formatKrw(f.total_krw) : formatMoney(f.amount, f.currency)}
          <span className="block text-[11px] font-normal text-gray-500">일행 합계 · 왕복</span>
        </p>
      </div>
      <LegLine label="가는 편" segs={segments(f, 'out')} />
      <LegLine label="오는 편" segs={segments(f, 'back')} />
      <div className="flex items-center justify-between gap-2 border-t border-gray-100 pt-2.5">
        <p className="text-xs text-gray-600">
          {f.usable_min !== null ? (
            <>
              현지 <strong className="text-gray-900">{formatSpan(f.usable_min)}</strong>
            </>
          ) : (
            '현지 시간 계산 불가'
          )}
          {f.krw_per_usable_hour !== null && ` · 1시간당 ${formatKrw(f.krw_per_usable_hour)}`}
        </p>
        <button
          type="button"
          disabled={add.isPending || add.isSuccess}
          onClick={() => add.mutate(f.id)}
          className={`${BTN.primary} min-h-10 shrink-0 px-3`}
        >
          {add.isSuccess ? '추가됨' : '후보로 추가'}
        </button>
      </div>
      {add.error && <p className="text-xs text-red-700">{add.error.message}</p>}
    </li>
  )
}

/** Live fares (Ignav), best value per usable hour first. */
export function LiveFares({ tripId }: { tripId: number }) {
  const fares = useFares(tripId)
  const prefs = useFarePrefs(tripId)
  const job = useJob('prices')
  const running = job.data?.running ?? false
  const [all, setAll] = useState(false)
  const [editing, setEditing] = useState(false)
  const invalidate = useMemo(
    () => [
      ['fares', tripId],
      ['hotels', tripId],
    ],
    [tripId],
  )
  const items = fares.data?.items ?? []
  const shown = all ? items : items.slice(0, 4)
  return (
    <div className={`${PANEL.live} space-y-3 p-4`}>
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 font-semibold">
            실시간 운임 <span className={BADGE.live}>자동 수집</span>
          </p>
          <p className="text-xs text-gray-500">
            {fetchedLabel(fares.data?.fetched_at)}
            {fares.data?.reference_label &&
              ` · 공항↔숙소는 ${fares.data.reference_label} 기준 근사`}
          </p>
        </div>
        <JobButton name="prices" label="새로 가져오기" tone="live" invalidate={invalidate} />
      </div>
      {prefs.data && (
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="flex w-full flex-wrap items-center gap-1.5 rounded-xl border border-sky-200 bg-white p-2 text-left"
        >
          {prefsChips(prefs.data).map((c) => (
            <span key={c} className="rounded-md bg-sky-50 px-2 py-0.5 text-xs text-sky-900">
              {c}
            </span>
          ))}
          <span className="ml-auto px-1 text-xs font-semibold text-sky-700">조건 바꾸기</span>
        </button>
      )}
      {editing && prefs.data && (
        <FarePrefsSheet tripId={tripId} prefs={prefs.data} onClose={() => setEditing(false)} />
      )}
      {!running && job.data?.last_status === 'error' && job.data.last_error && (
        <p className="text-xs text-red-700">{job.data.last_error}</p>
      )}
      {running ? (
        <LoadingBlock
          tone="live"
          title="운임을 가져오는 중…"
          hint="공항 조합마다 조회해서 1분 정도 걸립니다"
        />
      ) : items.length > 0 ? (
        <ul className="space-y-2.5">
          {shown.map((f) => (
            <FareRow key={f.id} f={f} tripId={tripId} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-gray-500">
          '새로 가져오기'를 누르면 위 조건으로 왕복 운임을 가져옵니다.
        </p>
      )}
      {!running && items.length > 4 && (
        <button
          type="button"
          onClick={() => setAll(!all)}
          className="min-h-10 w-full text-sm font-medium text-sky-800"
        >
          {all ? '접기' : `${items.length - 4}개 더 보기`}
        </button>
      )}
      <p className="text-[11px] text-gray-400">
        운임 출처: Ignav · 항공사 로고: Travelpayouts · 가격은 수시로 바뀌니 예약 전에 확인하세요
      </p>
    </div>
  )
}

function VacancyRow({ v, tripId }: { v: VacancyOut; tripId: number }) {
  const add = useAddOffer(tripId, 'hotels')
  return (
    <li className="flex gap-3 rounded-2xl border border-gray-200 bg-white p-2.5 shadow-sm">
      {v.thumbnail_url ? (
        <img
          src={v.thumbnail_url}
          alt=""
          loading="lazy"
          className="size-16 shrink-0 rounded-xl object-cover"
        />
      ) : (
        <span className="flex size-16 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-2xl">
          🏨
        </span>
      )}
      <div className="min-w-0 flex-1 space-y-1">
        <p className="line-clamp-2 text-sm font-medium">{v.name}</p>
        <p className="flex flex-wrap items-center gap-1 text-xs text-gray-600">
          {v.review_average !== null && (
            <span>
              ★ {v.review_average.toFixed(2)}
              <span className="text-gray-400"> ({v.review_count})</span>
            </span>
          )}
          {v.nearest_station && <span>· {v.nearest_station}역</span>}
          {v.bath_hint && <span className={BADGE.live}>욕조 언급</span>}
        </p>
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-semibold">
            {v.nightly_krw !== null ? formatKrw(v.nightly_krw) : '-'}
            <span className="text-xs font-normal text-gray-500">
              {' '}
              /박 {v.nightly_jpy !== null && `(${formatMoney(v.nightly_jpy, 'JPY')})`}
            </span>
          </p>
          <div className="flex shrink-0 gap-1.5">
            {v.reserve_url && (
              <a
                href={v.reserve_url}
                target="_blank"
                rel="noreferrer"
                aria-label="楽天トラベル에서 보기"
                className="flex min-h-9 items-center rounded-lg border border-gray-200 bg-white px-2"
              >
                <BrandIcon brand="rakuten" className="size-4" />
              </a>
            )}
            <button
              type="button"
              disabled={add.isPending || add.isSuccess}
              onClick={() => add.mutate(v.id)}
              className={`${BTN.primary} min-h-9 rounded-lg px-2.5 text-xs`}
            >
              {add.isSuccess ? '추가됨' : '후보로'}
            </button>
          </div>
        </div>
      </div>
    </li>
  )
}

/** Rakuten Travel vacancies around the top areas, cheapest first. */
export function LiveHotels({ tripId }: { tripId: number }) {
  const hotels = useHotels(tripId)
  const job = useJob('prices')
  const running = job.data?.running ?? false
  const invalidate = useMemo(
    () => [
      ['fares', tripId],
      ['hotels', tripId],
    ],
    [tripId],
  )
  const [open, setOpen] = useState<Record<string, boolean>>({})
  const data = hotels.data
  return (
    <div className={`${PANEL.live} space-y-3 p-4`}>
      <div className="flex items-center gap-2">
        <BrandIcon brand="rakuten" className="size-6 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 font-semibold">
            楽天トラベル 빈방 <span className={BADGE.live}>자동 수집</span>
          </p>
          <p className="text-xs text-gray-500">
            {fetchedLabel(data?.fetched_at)} · 역 반경 1km · 2인 1박 최저 요금
          </p>
        </div>
        <JobButton name="prices" label="새로 가져오기" tone="live" invalidate={invalidate} />
      </div>
      {running ? (
        <LoadingBlock tone="live" title="빈방을 가져오는 중…" hint="동네마다 차례로 조회합니다" />
      ) : (
        <>
          {data && data.areas.length === 0 && (
            <p className="text-sm text-gray-500">
              '새로 가져오기'를 누르면 상위 동네의 빈방을 가져옵니다.
            </p>
          )}
          {data?.areas.map((a) => {
            const shown = open[a.area] ? a.items : a.items.slice(0, 3)
            return (
              <div key={a.area} className="space-y-2">
                <p className="flex items-center gap-1.5 text-sm font-semibold">
                  <span className="text-lg">{a.emoji ?? '📍'}</span>
                  {a.area}
                  <span className="text-xs font-normal text-gray-500">{a.items.length}곳</span>
                </p>
                <ul className="space-y-2">
                  {shown.map((v) => (
                    <VacancyRow key={v.id} v={v} tripId={tripId} />
                  ))}
                </ul>
                {a.items.length > 3 && (
                  <button
                    type="button"
                    onClick={() => setOpen({ ...open, [a.area]: !open[a.area] })}
                    className="min-h-10 w-full text-sm font-medium text-sky-800"
                  >
                    {open[a.area] ? '접기' : `${a.items.length - 3}곳 더 보기`}
                  </button>
                )}
              </div>
            )
          })}
        </>
      )}
      {data && (
        <p className="text-[11px] text-gray-400">
          <a href={data.credit_url} target="_blank" rel="noreferrer" className="underline">
            {data.credit_text}
          </a>{' '}
          · 2박 이상은 첫날 요금 기준이라 총액은 예약 화면에서 확인하세요
        </p>
      )}
    </div>
  )
}
