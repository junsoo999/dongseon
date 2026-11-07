import { useState } from 'react'
import type { ItineraryOut, PlanEditOut } from '../api/client'
import {
  useAcceptPlanSuggestion,
  usePlanPreview,
  usePlanSuggestions,
  useRejectPlanSuggestion,
  useReviewJob,
  useStartReview,
} from '../api/hooks'
import { BADGE, BTN, PANEL } from '../lib/theme'
import { BottomSheet } from './BottomSheet'
import { DiffList } from './DiffList'
import { LoadingBlock } from './Loading'

const FOLDED = 3
const NOTES_FOLDED = 2
const md = (iso: string) => `${Number(iso.slice(5, 7))}/${Number(iso.slice(8, 10))}`

function EditCard({
  e,
  version,
  onPreview,
}: {
  e: PlanEditOut
  version: number
  onPreview: () => void
}) {
  return (
    <li className="space-y-1.5 p-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold">{e.title}</p>
        {e.applicable ? (
          <span className="shrink-0 rounded-md bg-teal-50 px-1.5 py-0.5 text-xs font-medium text-teal-800">
            적용 가능
          </span>
        ) : (
          <span className="shrink-0 rounded-md bg-amber-50 px-1.5 py-0.5 text-xs font-medium text-amber-800">
            적용 어려움
          </span>
        )}
      </div>
      <p className="text-sm text-gray-700">{e.reason}</p>
      {!e.applicable && e.problems.length > 0 && (
        <ul className="text-xs text-amber-800">
          {e.problems.map((p) => (
            <li key={p}>⚠ {p}</li>
          ))}
        </ul>
      )}
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] text-gray-400">
          {e.source === 'rain' && e.date ? `☔ ${md(e.date)} 비 오면 · ` : ''}
          버전 {e.itinerary_version} 기준
          {e.itinerary_version !== version ? ' (지금 버전으로 다시 확인)' : ''}
        </span>
        <button type="button" onClick={onPreview} className={`${BTN.soft} min-h-9 px-3`}>
          미리보기
        </button>
      </div>
    </li>
  )
}

/** AI review: start it, read notes, and preview / accept / reject each edit. */
export function PlanReviewPanel({ tripId, it }: { tripId: number; it: ItineraryOut }) {
  const suggestions = usePlanSuggestions(tripId)
  const job = useReviewJob(tripId)
  const start = useStartReview()
  const reject = useRejectPlanSuggestion(tripId)
  const [open, setOpen] = useState(false)
  const [previewing, setPreviewing] = useState<PlanEditOut | null>(null)
  const running = job.data?.running ?? false
  const data = suggestions.data
  const review = data?.reviews.find((r) => r.source === 'review')
  const rains = (data?.reviews ?? []).filter((r) => r.source === 'rain')
  const edits = [...(data?.edits ?? [])].sort((a, b) => Number(b.applicable) - Number(a.applicable))
  const shown = open ? edits : edits.slice(0, FOLDED)
  const notes = review?.notes ?? []
  const shownNotes = open ? notes : notes.slice(0, NOTES_FOLDED)
  const rainHidden = open ? 0 : rains.reduce((n, r) => n + Math.max(0, r.notes.length - 1), 0)
  const hidden = notes.length - shownNotes.length + edits.length - shown.length + rainHidden
  const failed = !running && job.data?.last_status && job.data.last_status !== 'ok'

  return (
    <div className={`${PANEL.ai} overflow-hidden`}>
      <div className="flex items-center gap-2 p-3">
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 font-semibold">
            AI 검토 <span className={BADGE.ai}>AI 제안</span>
          </p>
          <p className="text-xs text-gray-600">
            {edits.length > 0
              ? `고칠 점 ${edits.length}개 · 적용 가능 ${edits.filter((e) => e.applicable).length}개`
              : 'AI가 동선·휴무·식사를 보고 고칠 점을 제안합니다'}
          </p>
        </div>
        <button
          type="button"
          disabled={running || start.isPending}
          onClick={() => start.mutate({ id: it.id, body: { force: !!review } })}
          className={`${BTN.ai} shrink-0`}
        >
          {review ? '다시 검토' : '검토 받기'}
        </button>
      </div>
      {start.error && <p className="px-3 pb-2 text-xs text-red-700">{start.error.message}</p>}
      {failed && job.data?.last_error && (
        <p className="px-3 pb-2 text-xs text-red-700">검토 실패: {job.data.last_error}</p>
      )}
      {running ? (
        <div className="px-3 pb-3">
          <LoadingBlock
            tone="ai"
            title="Claude가 일정을 검토하는 중…"
            hint="1~2분 걸립니다. 제안마다 앱이 다시 맞춰 보고 경고를 확인합니다"
            rows={2}
          />
        </div>
      ) : (
        <>
          {shownNotes.length > 0 && (
            <ul className="space-y-1 px-3 pb-3 text-sm text-violet-950">
              {shownNotes.map((n) => (
                <li key={n}>💡 {n}</li>
              ))}
            </ul>
          )}
          {rains.map((r) => {
            const count = edits.filter((e) => e.source === 'rain' && e.date === r.date).length
            return (
              <div key={r.id} className="space-y-1 px-3 pb-3 text-sm text-violet-950">
                <p className="flex items-center justify-between gap-2 font-semibold">
                  <span>
                    ☔ {r.date ? md(r.date) : ''} 비 오면
                    {count > 0 ? ` · 대안 ${count}개` : ' · 바꿀 곳 없음 (이미 실내 위주)'}
                  </span>
                  <button
                    type="button"
                    onClick={() => reject.mutate(r.id)}
                    className="min-h-9 text-xs font-medium text-violet-800"
                  >
                    닫기
                  </button>
                </p>
                {(open ? r.notes : r.notes.slice(0, 1)).map((n) => (
                  <p key={n}>💡 {n}</p>
                ))}
              </div>
            )
          })}
          {edits.length > 0 && (
            <ul className="divide-y divide-violet-100 border-t border-violet-100 bg-white">
              {shown.map((e) => (
                <EditCard
                  key={e.id}
                  e={e}
                  version={it.version}
                  onPreview={() => setPreviewing(e)}
                />
              ))}
            </ul>
          )}
          {(hidden > 0 || open) && (
            <button
              type="button"
              onClick={() => setOpen(!open)}
              className="min-h-11 w-full border-t border-violet-100 bg-white text-sm font-medium text-violet-800"
            >
              {open ? '접기' : `메모·제안 ${hidden}개 더 보기`}
            </button>
          )}
          {review && edits.length === 0 && (
            <div className="flex items-center justify-between gap-2 px-3 pb-3 text-sm text-gray-600">
              <span>고칠 점 제안이 없습니다.</span>
              <button
                type="button"
                onClick={() => reject.mutate(review.id)}
                className="min-h-9 text-xs font-medium text-violet-800"
              >
                메모 지우기
              </button>
            </div>
          )}
        </>
      )}
      {previewing && (
        <PreviewSheet
          tripId={tripId}
          e={previewing}
          current={it}
          onClose={() => setPreviewing(null)}
        />
      )}
    </div>
  )
}

/** The edit applied to the current version (not saved), its new problems, and accept / reject. */
export function PreviewSheet({
  tripId,
  e,
  current,
  onClose,
}: {
  tripId: number
  e: PlanEditOut
  current: ItineraryOut
  onClose: () => void
}) {
  const preview = usePlanPreview(e.id)
  const accept = useAcceptPlanSuggestion(tripId)
  const reject = useRejectPlanSuggestion(tripId)
  const p = preview.data
  const error = preview.error ?? accept.error ?? reject.error

  return (
    <BottomSheet open title="AI 제안 미리보기" onClose={onClose}>
      <div className="space-y-3">
        <div className={`${PANEL.ai} space-y-1 p-3`}>
          <p className="flex items-center gap-2 text-sm font-semibold">
            {e.title} <span className={BADGE.ai}>AI 제안</span>
          </p>
          <p className="text-sm text-gray-700">{e.reason}</p>
        </div>
        {preview.isPending ? (
          <LoadingBlock tone="live" title="지금 일정에 적용해 보는 중…" rows={1} />
        ) : p ? (
          <div className="space-y-2 rounded-2xl border border-gray-200 p-3">
            <p className="text-sm font-semibold">바뀌는 점 (버전 {current.version} → 새 버전)</p>
            <DiffList from={current} to={p.itinerary} />
            {p.resolved && (
              <p className="text-[11px] text-gray-500">
                경고를 줄이려고 바뀌는 날의 순서를 다시 맞췄습니다.
              </p>
            )}
            {p.problems.length > 0 && (
              <ul className="rounded-xl bg-amber-50 p-2 text-xs text-amber-900">
                <li className="font-semibold">적용하면 생기는 문제</li>
                {p.problems.map((x) => (
                  <li key={x}>⚠ {x}</li>
                ))}
              </ul>
            )}
          </div>
        ) : null}
        {error && <p className="text-sm text-red-700">{error.message}</p>}
        <div className="flex gap-2">
          <button
            type="button"
            disabled={reject.isPending}
            onClick={() => reject.mutate(e.id, { onSuccess: onClose })}
            className={BTN.secondary}
          >
            거절
          </button>
          <button
            type="button"
            disabled={!p?.applicable || accept.isPending}
            onClick={() => accept.mutate(e.id, { onSuccess: onClose })}
            className={`${BTN.primary} flex-1`}
          >
            {accept.isPending
              ? '저장 중…'
              : p && !p.applicable
                ? '적용할 수 없음'
                : '수락하고 새 버전 만들기'}
          </button>
        </div>
        <p className="text-[11px] text-gray-400">
          AI는 시각을 정하지 않습니다. 앱이 제안대로 바꿔 다시 계산하고, 새 경고가 없을 때만 적용할
          수 있습니다.
        </p>
      </div>
    </BottomSheet>
  )
}
