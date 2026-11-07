import { useMemo, useState } from 'react'
import { useHoursResearch, useJob } from '../api/hooks'
import { BADGE, PANEL } from '../lib/theme'
import { JobButton } from './JobButton'
import { LoadingBlock } from './Loading'

const md = (iso: string) => `${Number(iso.slice(5, 7))}/${Number(iso.slice(8, 10))}`

/** AI research of opening hours on holiday dates for must/want pins, with sources. */
export function HolidayHours({ tripId }: { tripId: number }) {
  const research = useHoursResearch(tripId)
  const job = useJob('hours-research')
  const [open, setOpen] = useState(false)
  const invalidate = useMemo(() => [['hoursResearch', tripId]], [tripId])
  const data = research.data
  if (!data || data.dates.length === 0) return null
  const running = job.data?.running ?? false
  const found = data.places.filter((p) => p.days.length > 0)
  const failed = !running && job.data?.last_status && job.data.last_status !== 'ok'

  return (
    <div className={`${PANEL.ai} overflow-hidden`}>
      <div className="flex items-center gap-2 p-3">
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 font-semibold">
            연휴 영업시간 조사 <span className={BADGE.ai}>AI 조사</span>
          </p>
          <p className="text-xs text-gray-600">
            {md(data.dates[0])}~{md(data.dates[data.dates.length - 1])} · 꼭·가고 싶은 곳{' '}
            {data.places.length}곳 중 {found.length}곳 확인
          </p>
        </div>
        <JobButton name="hours-research" label="조사하기" tone="ai" invalidate={invalidate} />
      </div>
      {failed && job.data?.last_error && (
        <p className="px-3 pb-2 text-xs text-red-700">조사 실패: {job.data.last_error}</p>
      )}
      {running ? (
        <div className="px-3 pb-3">
          <LoadingBlock
            tone="ai"
            title="Claude가 연휴 영업 여부를 찾는 중…"
            hint="공식 페이지를 확인하며 조사해서 몇 분 걸립니다"
            rows={1}
          />
        </div>
      ) : found.length > 0 ? (
        <div className="border-t border-violet-100 bg-white px-3 py-2">
          <button
            type="button"
            onClick={() => setOpen(!open)}
            className="min-h-9 text-sm font-medium text-violet-800"
          >
            {open ? '결과 접기' : '조사 결과 보기'}
          </button>
          {open && (
            <ul className="space-y-2 pb-1">
              {found.map((p) => (
                <li key={p.pin_id} className="text-sm">
                  <p className="font-medium">{p.label}</p>
                  <p className="flex flex-wrap gap-1.5">
                    {p.days.map((d) => (
                      <a
                        key={d.date}
                        href={d.source_url ?? undefined}
                        target="_blank"
                        rel="noreferrer"
                        className={`rounded-md px-1.5 py-0.5 text-xs ${d.status === 'closed' ? 'bg-red-50 text-red-800' : 'bg-teal-50 text-teal-800'}`}
                      >
                        {md(d.date)} {d.status === 'closed' ? '휴무' : `${d.open}~${d.close}`} ↗
                      </a>
                    ))}
                  </p>
                </li>
              ))}
            </ul>
          )}
          <p className="text-[11px] text-gray-500">
            AI 조사 결과라 확인이 필요합니다. 일정에 반영하려면 '다시 맞추기'를 누르세요. 직접
            입력한 영업시간이 있으면 그것이 먼저입니다.
          </p>
        </div>
      ) : job.data?.last_status === 'ok' && job.data.last_ran_at ? (
        <p className="px-3 pb-3 text-xs text-gray-600">
          아직 그날 영업 여부를 밝힌 공식 공지를 찾지 못했습니다. 연말연시 공지는 보통 12월
          초·중순에 올라오니 그때 다시 조사해 보세요.
        </p>
      ) : (
        <p className="px-3 pb-3 text-xs text-gray-600">
          연휴에는 쉬는 곳이 많습니다. 공식 페이지에서 그날 영업 여부를 찾아 일정에 반영합니다.
        </p>
      )}
    </div>
  )
}
