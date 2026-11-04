import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { useJob, useStartJob } from '../api/hooks'

/** Starts a background job and refreshes `invalidate` query keys when it finishes. */
export function JobButton({
  name,
  label,
  invalidate,
}: {
  name: 'scout' | 'prices'
  label: string
  invalidate: unknown[][]
}) {
  const job = useJob(name)
  const start = useStartJob(name)
  const qc = useQueryClient()
  const wasRunning = useRef(false)
  const running = job.data?.running ?? false

  useEffect(() => {
    if (wasRunning.current && !running)
      for (const key of invalidate) void qc.invalidateQueries({ queryKey: key })
    wasRunning.current = running
  }, [running, qc, invalidate])

  return (
    <button
      type="button"
      disabled={running || start.isPending}
      onClick={() => start.mutate()}
      className="min-h-11 shrink-0 rounded-xl border border-gray-300 bg-white px-3 text-sm disabled:opacity-50"
    >
      {running ? '가져오는 중…' : label}
    </button>
  )
}
