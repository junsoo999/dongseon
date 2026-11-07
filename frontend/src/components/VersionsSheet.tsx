import { useState } from 'react'
import type { ItineraryOut } from '../api/client'
import { useItinerary, useItineraryVersions } from '../api/hooks'
import { diffVersions } from '../lib/itineraryDiff'
import { BTN } from '../lib/theme'
import { BottomSheet } from './BottomSheet'

const ORIGIN: Record<string, string> = { solver: '자동 계산', user: '직접 수정', ai: 'AI 제안' }
const KIND_STYLE: Record<string, string> = {
  added: 'text-teal-700',
  removed: 'text-red-700',
  moved: 'text-sky-700',
  retimed: 'text-gray-600',
}

function when(iso: string): string {
  return new Date(iso).toLocaleString('ko-KR', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Version history: pick an older version to see what restoring it would change, and restore it. */
export function VersionsSheet({
  tripId,
  current,
  restoring,
  onRestore,
  onClose,
}: {
  tripId: number
  current: ItineraryOut
  restoring: boolean
  onRestore: (id: number) => void
  onClose: () => void
}) {
  const versions = useItineraryVersions(tripId)
  const [picked, setPicked] = useState<number | null>(null)
  const other = useItinerary(picked)
  const diff = other.data ? diffVersions(current, other.data) : null

  return (
    <BottomSheet open title="버전 기록" onClose={onClose}>
      <ul className="space-y-1.5">
        {(versions.data ?? []).map((v) => {
          const isCurrent = v.id === current.id
          const on = v.id === picked
          return (
            <li key={v.id}>
              <button
                type="button"
                disabled={isCurrent}
                onClick={() => setPicked(on ? null : v.id)}
                className={`flex min-h-11 w-full items-center justify-between gap-2 rounded-xl px-3 text-left text-sm ${on ? 'bg-teal-50 ring-1 ring-teal-300' : 'border border-gray-200'}`}
              >
                <span>
                  <span className="font-semibold">버전 {v.version}</span>
                  <span className="ml-2 text-gray-500">
                    {ORIGIN[v.origin] ?? v.origin} · {when(v.created_at)}
                  </span>
                </span>
                <span className="shrink-0 text-xs text-gray-500">
                  {isCurrent ? (
                    <span className="rounded bg-teal-700 px-1.5 py-0.5 text-white">현재</span>
                  ) : (
                    `방문 ${v.visits}곳`
                  )}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
      {picked !== null && (
        <div className="mt-4 space-y-3 rounded-2xl border border-gray-200 p-3">
          <p className="text-sm font-semibold">
            되돌리면 바뀌는 점 (현재 버전 {current.version} → 버전 {other.data?.version ?? '…'})
          </p>
          {diff && diff.length === 0 && <p className="text-sm text-gray-500">차이가 없습니다.</p>}
          {diff?.map((g) => (
            <div key={g.date}>
              <p className="text-xs font-semibold text-gray-500">
                {Number(g.date.slice(5, 7))}/{Number(g.date.slice(8, 10))}
              </p>
              <ul className="text-sm">
                {g.changes.map((c) => (
                  <li key={`${c.kind}-${c.pinId}`} className="flex justify-between gap-2">
                    <span className="truncate">{c.label}</span>
                    <span className={`shrink-0 ${KIND_STYLE[c.kind]}`}>{c.text}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          <button
            type="button"
            disabled={restoring || !other.data}
            onClick={() => onRestore(picked)}
            className={`${BTN.primary} w-full`}
          >
            버전 {other.data?.version ?? ''}으로 되돌리기
          </button>
          <p className="text-[11px] text-gray-400">
            되돌리면 그 버전의 순서로 새 버전을 만들고, 시각은 지금 영업시간 기준으로 다시
            계산합니다.
          </p>
        </div>
      )}
    </BottomSheet>
  )
}
