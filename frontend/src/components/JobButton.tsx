import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { useJob, useStartJob, type JobName } from '../api/hooks'
import { BTN, type Tone } from '../lib/theme'

/** Starts a background job and refreshes `invalidate` query keys when it finishes. */
export function JobButton({
  name,
  label,
  invalidate,
  tone,
}: {
  name: JobName
  label: string
  invalidate: unknown[][]
  tone: Tone
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
      className={`${BTN[tone]} shrink-0 px-3`}
    >
      {running && (
        <span
          aria-hidden
          className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white"
        />
      )}
      {running ? (tone === 'ai' ? '찾는 중' : '가져오는 중') : label}
    </button>
  )
}
