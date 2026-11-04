import type { Tone } from '../lib/theme'

const TONE = {
  ai: {
    ring: 'border-violet-200 border-t-violet-600',
    bar: 'bg-violet-100',
    text: 'text-violet-800',
  },
  live: { ring: 'border-sky-200 border-t-sky-600', bar: 'bg-sky-100', text: 'text-sky-800' },
}

/** A spinner with skeleton rows, shown while a background job runs. */
export function LoadingBlock({
  tone,
  title,
  hint,
  rows = 3,
}: {
  tone: Tone
  title: string
  hint?: string
  rows?: number
}) {
  const t = TONE[tone]
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <div className="flex items-center gap-3">
        <span
          aria-hidden
          className={`size-6 shrink-0 animate-spin rounded-full border-[3px] ${t.ring}`}
        />
        <div>
          <p className={`text-sm font-semibold ${t.text}`}>{title}</p>
          {hint && <p className="text-xs text-gray-500">{hint}</p>}
        </div>
      </div>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="animate-pulse space-y-2 rounded-2xl bg-white p-3">
          <div className="flex items-center gap-3">
            <div className={`size-9 rounded-xl ${t.bar}`} />
            <div className="flex-1 space-y-2">
              <div className={`h-3 w-3/4 rounded ${t.bar}`} />
              <div className={`h-3 w-1/2 rounded ${t.bar}`} />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
