import { useEffect, useState } from 'react'
import type { SuggestionOut } from '../api/client'
import { useAutocomplete } from '../api/hooks'
import { GoogleAttribution } from './GoogleAttribution'

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

/** Type-ahead search over Google places. Suggestion text is display-only and never saved. */
export function SearchPicker({
  tripId,
  sessionToken,
  onPick,
  placeholder = '장소 이름으로 검색',
  initialQuery = '',
}: {
  tripId: number
  sessionToken: string
  onPick: (s: SuggestionOut, query: string) => void
  placeholder?: string
  initialQuery?: string
}) {
  const [query, setQuery] = useState(initialQuery)
  const debounced = useDebounced(query, 300)
  const { data, isFetching, error } = useAutocomplete(tripId, debounced, sessionToken)
  const showList = debounced.trim().length >= 2

  return (
    <div>
      <input
        type="search"
        autoFocus
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={placeholder}
        className="min-h-11 w-full rounded-lg border border-gray-300 px-3 text-base"
      />
      {error && <p className="mt-2 text-sm text-red-700">{error.message}</p>}
      {showList && !error && (
        <div className="mt-2 rounded-lg border border-gray-200">
          {data && data.length > 0 ? (
            <ul className="divide-y divide-gray-100">
              {data.map((s) => (
                <li key={s.google_place_id}>
                  <button
                    type="button"
                    onClick={() => onPick(s, query.trim())}
                    className="flex min-h-12 w-full flex-col items-start px-3 py-2 text-left hover:bg-gray-50"
                  >
                    <span className="font-medium">{s.main_text}</span>
                    <span className="text-xs text-gray-500">{s.secondary_text}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-3 py-3 text-sm text-gray-500">
              {isFetching ? '찾는 중…' : '결과가 없습니다'}
            </p>
          )}
          <div className="border-t border-gray-100 px-3 py-1.5 text-right">
            <GoogleAttribution />
          </div>
        </div>
      )}
    </div>
  )
}
