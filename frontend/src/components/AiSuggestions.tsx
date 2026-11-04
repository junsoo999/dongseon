import { useMemo, useState } from 'react'
import type { AiSuggestionOut } from '../api/client'
import { useDecideSuggestion, useJob, useSuggestions } from '../api/hooks'
import { formatLocal } from '../lib/format'
import { categoryLabel, MEAL_LABELS } from '../lib/places'
import { BADGE, BTN, PANEL } from '../lib/theme'
import { JobButton } from './JobButton'
import { LoadingBlock } from './Loading'

const RESERVATION: Record<string, string> = {
  required: '예약 필수',
  recommended: '예약 권장',
  not_needed: '예약 없이',
  unknown: '',
}
const FOLDED = 3

const STAY_TYPE: Record<string, string> = {
  hotel: '호텔',
  apartment_hotel: '레지던스',
  ryokan: '료칸',
  other: '숙소',
}

function Sources({ s }: { s: { title: string; url: string }[] }) {
  return (
    <p className="text-xs text-gray-500">
      출처:{' '}
      {s.map((src, i) => (
        <span key={src.url}>
          {i > 0 && ', '}
          <a href={src.url} target="_blank" rel="noreferrer" className="text-teal-700 underline">
            {src.title || '링크'}
          </a>
        </span>
      ))}
    </p>
  )
}

function Card({ s, tripId }: { s: AiSuggestionOut; tripId: number }) {
  const decide = useDecideSuggestion(tripId)
  const p = s.place
  const st = s.stay
  const title = p?.name ?? st?.name ?? ''
  const local = p?.name_local ?? st?.name_local
  const meta = p
    ? [
        p.area,
        categoryLabel(p.category),
        p.meal ? MEAL_LABELS[p.meal] : null,
        RESERVATION[p.reservation],
        p.price_range,
      ]
    : st
      ? [
          st.area,
          STAY_TYPE[st.type],
          st.has_bathtub === true ? '욕조 있음' : st.has_bathtub === false ? '욕조 없음' : null,
          st.nightly_low != null && st.nightly_high != null
            ? `1박 ${st.nightly_low.toLocaleString('ko-KR')}~${st.nightly_high.toLocaleString('ko-KR')} ${st.currency}`
            : null,
        ]
      : []
  return (
    <li className="space-y-1 p-4">
      <p className="flex flex-wrap items-baseline gap-x-2">
        <span className="font-medium">{title}</span>
        {local && local !== title && <span className="text-xs text-gray-500">{local}</span>}
      </p>
      <p className="text-xs text-gray-600">{meta.filter(Boolean).join(' · ')}</p>
      <p className="text-sm">{p?.why ?? st?.why}</p>
      {p?.holiday_note && <p className="text-xs text-amber-700">{p.holiday_note}</p>}
      {st?.price_note && <p className="text-xs text-gray-500">{st.price_note}</p>}
      {!s.google_place_id && <p className="text-xs text-amber-700">지도 위치를 찾지 못했습니다</p>}
      <Sources s={p?.sources ?? st?.sources ?? []} />
      {decide.error && <p className="text-xs text-red-700">{decide.error.message}</p>}
      <div className="flex gap-2 pt-1">
        <button
          type="button"
          disabled={decide.isPending || (s.kind === 'stay' && !s.google_place_id)}
          onClick={() => decide.mutate({ id: s.id, accept: true })}
          className={`${BTN.primary} flex-1`}
        >
          {s.kind === 'place' ? '여행에 넣기' : '숙소 후보로'}
        </button>
        <button
          type="button"
          disabled={decide.isPending}
          onClick={() => decide.mutate({ id: s.id, accept: false })}
          className={`${BTN.secondary} flex-1`}
        >
          관심 없음
        </button>
      </div>
    </li>
  )
}

/** AI recommendations with a "find more" button that runs the background scout job. */
export function AiSuggestions({ tripId, kind }: { tripId: number; kind: 'place' | 'stay' }) {
  const suggestions = useSuggestions(tripId, kind)
  const job = useJob('scout')
  const running = job.data?.running ?? false
  const invalidate = useMemo(() => [['suggestions', tripId]], [tripId])
  const list = suggestions.data ?? []
  const [open, setOpen] = useState(false)
  const shown = open ? list : list.slice(0, FOLDED)

  return (
    <div className={`${PANEL.ai} overflow-hidden`}>
      <div className="flex items-center gap-2 p-4">
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 font-semibold">
            AI 추천 <span className={BADGE.ai}>AI 제안</span>
          </p>
          <p className="text-xs text-gray-600">
            {job.data?.last_ran_at
              ? `마지막 조사 ${formatLocal(job.data.last_ran_at.slice(0, 16))} UTC${job.data.last_status && job.data.last_status !== 'ok' ? ' · 실패' : ''}`
              : '아직 조사하지 않았습니다'}
          </p>
        </div>
        <JobButton name="scout" label="새로 찾기" tone="ai" invalidate={invalidate} />
      </div>
      {!running &&
        job.data?.last_status &&
        job.data.last_status !== 'ok' &&
        job.data.last_error && (
          <p className="px-4 pb-2 text-xs text-red-700">{job.data.last_error}</p>
        )}
      {running ? (
        <div className="px-4 pb-4">
          <LoadingBlock
            tone="ai"
            title="Claude가 웹에서 찾는 중…"
            hint="출처를 확인하며 조사해서 몇 분 걸립니다"
          />
        </div>
      ) : list.length > 0 ? (
        <ul className="divide-y divide-violet-100 border-t border-violet-100 bg-white">
          {shown.map((s) => (
            <Card key={s.id} s={s} tripId={tripId} />
          ))}
          {list.length > FOLDED && (
            <li>
              <button
                type="button"
                onClick={() => setOpen(!open)}
                className="min-h-11 w-full text-sm font-medium text-violet-800"
              >
                {open ? '접기' : `추천 ${list.length - FOLDED}개 더 보기`}
              </button>
            </li>
          )}
        </ul>
      ) : (
        <p className="px-4 pb-4 text-sm text-gray-500">
          새 추천이 없습니다. '새로 찾기'를 눌러 보세요.
        </p>
      )}
    </div>
  )
}
