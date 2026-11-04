import type { LinkOut } from '../api/client'
import { useSearchLinks } from '../api/hooks'
import { isBrand } from '../lib/brands'
import { BrandIcon } from './BrandIcon'

const SITE_NAME: Record<string, string> = {
  airbnb: 'Airbnb',
  booking: 'Booking.com',
  google_flights: 'Google 항공권',
  naver: '네이버 항공권',
}

function SiteButton({ link }: { link: LinkOut }) {
  return (
    <a
      href={link.url}
      target="_blank"
      rel="noreferrer"
      className="flex min-h-11 items-center justify-center gap-2 rounded-xl border border-gray-200 bg-white px-3 text-sm font-medium shadow-sm hover:border-gray-300 hover:bg-gray-50"
    >
      {isBrand(link.site) && <BrandIcon brand={link.site} className="size-5 shrink-0" />}
      <span className="truncate">{SITE_NAME[link.site] ?? link.label}</span>
    </a>
  )
}

/** Flight searches with the route, dates and travelers filled in. */
export function FlightSearchLinks({ tripId }: { tripId: number }) {
  const links = useSearchLinks(tripId)
  const flights = links.data?.flights ?? []
  if (flights.length === 0) return null
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4">
      <p className="mb-1 font-semibold">항공권 찾아보기</p>
      <p className="mb-3 text-xs text-gray-500">
        여행 날짜·인원이 채워진 검색이 열립니다. 고른 편은 '+ 항공 후보'로 넣으세요.
      </p>
      <div className="grid grid-cols-2 gap-2">
        {flights.map((l) => (
          <SiteButton key={l.url} link={l} />
        ))}
      </div>
    </div>
  )
}

/** Airbnb and Booking.com searches for the best-ranked areas. */
export function StaySearchLinks({ tripId, top = 3 }: { tripId: number; top?: number }) {
  const links = useSearchLinks(tripId)
  const areas = (links.data?.stays ?? []).slice(0, top)
  if (areas.length === 0) return null
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4">
      <p className="mb-1 font-semibold">숙소 찾아보기</p>
      <p className="mb-3 text-xs text-gray-500">
        순위가 높은 동네의 검색이 날짜·인원이 채워진 채로 열립니다. 욕조 같은 조건은 열린 화면의
        필터에서 고르세요.
      </p>
      <ul className="space-y-3">
        {areas.map((a) => (
          <li key={a.area}>
            <p className="mb-1.5 flex items-center gap-1.5 text-sm font-medium">
              <span className="text-lg">{a.emoji ?? '📍'}</span>
              {a.area}
              {a.rank !== null && (
                <span className="text-xs font-normal text-gray-500">{a.rank}위</span>
              )}
            </p>
            <div className="grid grid-cols-2 gap-2">
              {a.links.map((l) => (
                <SiteButton key={l.url} link={l} />
              ))}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
