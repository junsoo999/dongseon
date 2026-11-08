import { useMemo } from 'react'
import type { LocalNameOut } from '../api/client'
import {
  useAcceptLocalName,
  useAcceptVerifiedLocalNames,
  useJob,
  useLocalNames,
  useRejectLocalName,
} from '../api/hooks'
import { BADGE, BTN, PANEL } from '../lib/theme'
import { JobButton } from './JobButton'

function SuggestionRow({ tripId, s }: { tripId: number; s: LocalNameOut }) {
  const accept = useAcceptLocalName(tripId)
  const reject = useRejectLocalName(tripId)
  const busy = accept.isPending || reject.isPending
  return (
    <li className="space-y-1 rounded-xl bg-white p-3">
      <p className="text-sm">
        <span className="text-gray-600">{s.label}</span> →{' '}
        <span className="font-semibold" lang="ja">
          {s.name_local}
        </span>
      </p>
      <p className="flex flex-wrap items-center gap-x-2 text-xs text-gray-500">
        {s.verified ? (
          <span className="font-medium text-teal-800">✓ Google 검색으로 같은 장소 확인</span>
        ) : (
          <span className="font-medium text-amber-800">확인 필요 (검색에 이 장소가 안 나옴)</span>
        )}
        <span>AI 제안 · 출처:</span>
        {s.sources.map((x) => (
          <a key={x.url} href={x.url} target="_blank" rel="noreferrer" className="underline">
            {x.title}
          </a>
        ))}
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => accept.mutate(s.id)}
          className={`${BTN.soft} flex-1`}
        >
          적용
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => reject.mutate(s.id)}
          className={`${BTN.secondary} flex-1`}
        >
          아니에요
        </button>
      </div>
    </li>
  )
}

/** AI research of local-language names, so My Maps finds each place by its own name. */
export function LocalNames({ tripId }: { tripId: number }) {
  const data = useLocalNames(tripId)
  const job = useJob('local-names')
  const applyVerified = useAcceptVerifiedLocalNames(tripId)
  const invalidate = useMemo(() => [['localNames', tripId]], [tripId])
  if (!data.data) return null
  const { total, filled, suggestions } = data.data
  if (total === 0) return null
  const running = job.data?.running ?? false
  const failed = !running && job.data?.last_status && job.data.last_status !== 'ok'
  const verified = suggestions.filter((s) => s.verified).length
  const missing = total - filled
  return (
    <div className={`${PANEL.ai} space-y-3 p-3`}>
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 text-sm font-semibold">
            현지 이름 {filled}/{total}곳 <span className={BADGE.ai}>AI 조사</span>
          </p>
          <p className="text-xs text-gray-600">
            {running
              ? 'Claude가 일본어 이름을 찾는 중… (몇 분)'
              : failed
                ? `조사 실패: ${job.data?.last_error ?? ''}`
                : missing === 0
                  ? '모든 장소에 현지 이름이 있습니다'
                  : '내 지도가 장소를 이름으로 찾습니다. 비어 있는 곳의 일본어 이름을 출처와 함께 찾아봅니다'}
          </p>
        </div>
        {missing > suggestions.length && (
          <JobButton name="local-names" label="AI로 채우기" tone="ai" invalidate={invalidate} />
        )}
      </div>
      {verified > 0 && (
        <button
          type="button"
          disabled={applyVerified.isPending}
          onClick={() => applyVerified.mutate(undefined)}
          className={`${BTN.primary} w-full`}
        >
          확인된 {verified}곳 모두 적용
        </button>
      )}
      {suggestions.length > 0 && (
        <ul className="space-y-2">
          {suggestions.map((s) => (
            <SuggestionRow key={s.id} tripId={tripId} s={s} />
          ))}
        </ul>
      )}
    </div>
  )
}
