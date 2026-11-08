import { useEffect } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router'
import { tripInProgress } from '../lib/today'
import { useCurrentTrip } from '../lib/trip'
import { HealthBadge } from './HealthBadge'

const OPENED_KEY = 'dongseon.opened'

/** During the trip the app opens on 오늘 (once per browser tab, so 홈 stays reachable). */
function useTodayFirst() {
  const { trip } = useCurrentTrip()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  useEffect(() => {
    if (!trip) return
    let opened = true
    try {
      opened = window.sessionStorage.getItem(OPENED_KEY) === '1'
      window.sessionStorage.setItem(OPENED_KEY, '1')
    } catch {
      opened = true
    }
    if (!opened && pathname === '/' && tripInProgress(trip)) navigate('/today', { replace: true })
  }, [trip, pathname, navigate])
}

/** Every screen, in desktop header order. */
const NAV = [
  { to: '/', label: '홈' },
  { to: '/places', label: '장소' },
  { to: '/stays', label: '숙소' },
  { to: '/flights', label: '항공' },
  { to: '/itinerary', label: '일정' },
  { to: '/today', label: '오늘' },
  { to: '/prep', label: '준비' },
  { to: '/settings', label: '설정' },
]

/** The phone tab bar keeps five tabs; the rest live under 더보기. */
const TABS = [
  { to: '/', label: '홈' },
  { to: '/places', label: '장소' },
  { to: '/itinerary', label: '일정' },
  { to: '/today', label: '오늘' },
  { to: '/more', label: '더보기' },
]

const linkClass = ({ isActive }: { isActive: boolean }) =>
  isActive ? 'font-semibold text-teal-700' : 'text-gray-600 hover:text-gray-900'

export function Layout() {
  useTodayFirst()
  return (
    <div className="flex min-h-dvh flex-col bg-gray-50 pb-16 text-gray-900 tabular-nums md:h-dvh md:pb-0">
      <header className="hidden shrink-0 items-center gap-6 border-b border-gray-200 bg-white px-6 py-3 md:flex">
        <NavLink to="/" className="flex items-center gap-2 text-lg font-extrabold tracking-tight">
          <img src="/icon.svg" alt="" className="size-7 rounded-lg" />
          dongseon
        </NavLink>
        <nav aria-label="주 메뉴" className="flex gap-5 text-[15px]">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === '/'} className={linkClass}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto">
          <HealthBadge />
        </div>
      </header>

      <main className="min-h-0 flex-1 md:overflow-y-auto">
        <Outlet />
      </main>

      <nav
        aria-label="하단 메뉴"
        className="fixed inset-x-0 bottom-0 z-30 grid h-16 grid-cols-5 border-t border-gray-200 bg-white pb-[env(safe-area-inset-bottom)] md:hidden"
      >
        {TABS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex min-h-11 items-center justify-center text-[13px] ${linkClass({ isActive })}`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
