import type { ItineraryOut } from '../api/client'
import { diffVersions } from '../lib/itineraryDiff'

const KIND_STYLE: Record<string, string> = {
  added: 'text-teal-700',
  removed: 'text-red-700',
  moved: 'text-sky-700',
  retimed: 'text-gray-600',
}

/** What changes from ``from`` to ``to``, grouped by date. */
export function DiffList({ from, to }: { from: ItineraryOut; to: ItineraryOut }) {
  const diff = diffVersions(from, to)
  if (diff.length === 0) return <p className="text-sm text-gray-500">차이가 없습니다.</p>
  return (
    <>
      {diff.map((g) => (
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
    </>
  )
}
