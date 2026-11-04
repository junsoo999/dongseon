import { useSearchLinks } from '../api/hooks'

const linkClass =
  'flex min-h-11 items-center justify-center rounded-lg border border-gray-300 bg-white px-3 text-sm'

/** Flight searches with the route, dates and travelers filled in. */
export function FlightSearchLinks({ tripId }: { tripId: number }) {
  const links = useSearchLinks(tripId)
  const flights = links.data?.flights ?? []
  if (flights.length === 0) return null
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3">
      <p className="mb-2 text-sm font-semibold">항공권 검색 열기</p>
      <div className="grid grid-cols-2 gap-2">
        {flights.map((l) => (
          <a key={l.url} href={l.url} target="_blank" rel="noreferrer" className={linkClass}>
            {l.label}
          </a>
        ))}
      </div>
      <p className="mt-2 text-xs text-gray-500">
        여행 날짜·인원이 채워진 검색이 열립니다. 마음에 드는 편을 '+ 항공 후보'로 넣으세요.
      </p>
    </div>
  )
}

/** Airbnb and Booking.com searches for the best-ranked areas. */
export function StaySearchLinks({ tripId, top = 3 }: { tripId: number; top?: number }) {
  const links = useSearchLinks(tripId)
  const areas = (links.data?.stays ?? []).slice(0, top)
  if (areas.length === 0) return null
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3">
      <p className="mb-2 text-sm font-semibold">에어비앤비·호텔 검색 열기</p>
      <ul className="space-y-2">
        {areas.map((a) => (
          <li key={a.area} className="grid grid-cols-[5.5rem_1fr_1fr] items-center gap-2">
            <span className="truncate text-sm">
              {a.rank !== null && <span className="mr-1 text-xs text-gray-500">{a.rank}위</span>}
              {a.area}
            </span>
            {a.links.map((l) => (
              <a key={l.url} href={l.url} target="_blank" rel="noreferrer" className={linkClass}>
                {l.label}
              </a>
            ))}
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-gray-500">
        날짜·인원이 채워진 검색이 열립니다. 욕조 같은 조건은 열린 화면의 필터에서 고르고, 마음에
        드는 곳은 링크와 함께 '+ 숙소 후보'로 넣으세요.
      </p>
    </div>
  )
}
