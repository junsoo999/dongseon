import { useMemo, useState } from 'react'
import type { AreaNoteOut } from '../api/client'
import { useJob } from '../api/hooks'
import { BADGE } from '../lib/theme'
import { JobButton } from './JobButton'

/** The row that starts AI area research. */
export function AreaNotesBar({ tripId, count }: { tripId: number; count: number }) {
  const job = useJob('area-notes')
  const invalidate = useMemo(() => [['areaNotes', tripId]], [tripId])
  const running = job.data?.running ?? false
  const failed = !running && job.data?.last_status && job.data.last_status !== 'ok'
  return (
    <div className="flex items-center gap-2 rounded-2xl border border-violet-200 bg-violet-50/60 p-3">
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-2 text-sm font-semibold">
          동네 메모 <span className={BADGE.ai}>AI 조사</span>
        </p>
        <p className="text-xs text-gray-600">
          {running
            ? 'Claude가 동네 분위기와 장단점을 찾는 중… (몇 분)'
            : failed
              ? `조사 실패: ${job.data?.last_error ?? ''}`
              : count > 0
                ? `${count}개 동네에 분위기·장단점 메모가 있습니다 (출처 포함)`
                : '동네마다 분위기·소음·편의시설을 출처와 함께 찾아봅니다'}
        </p>
      </div>
      <JobButton
        name="area-notes"
        label={count > 0 ? '다시 찾기' : '메모 찾기'}
        tone="ai"
        invalidate={invalidate}
      />
    </div>
  )
}

/** One area's AI note under its ranking row. */
export function AreaNoteLine({ note }: { note: AreaNoteOut }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="px-3 pt-1 text-xs text-violet-950">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="min-h-8 w-full text-left"
        aria-expanded={open}
      >
        💬 {note.summary} <span className="text-violet-700">{open ? '접기' : '자세히'}</span>
      </button>
      {open && (
        <div className="space-y-1 pb-1">
          {note.pros.map((p) => (
            <p key={p}>👍 {p}</p>
          ))}
          {note.cons.map((c) => (
            <p key={c}>👎 {c}</p>
          ))}
          <p className="flex flex-wrap gap-x-2 text-gray-500">
            AI 제안 · 출처:
            {note.sources.map((s) => (
              <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className="underline">
                {s.title}
              </a>
            ))}
          </p>
        </div>
      )}
    </div>
  )
}
