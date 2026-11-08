import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { _clearMemory, saveBundle } from '../lib/offline'
import { mockApi } from '../test/mockApi'
import { Today } from './Today'

const trip = {
  id: 1,
  title: '도쿄',
  city_key: 'tokyo',
  city_name: '도쿄',
  start_date: '2030-12-28',
  end_date: '2030-12-29',
  timezone: 'Asia/Tokyo',
  pace: 'normal',
  status: 'planning',
  pin_count: 2,
  center_lat: null,
  center_lng: null,
}
const stop = (id: number, label: string, start: string, end: string) => ({
  id,
  pin_id: id,
  label,
  kind: 'visit',
  category: 'museum',
  priority: 'must',
  google_place_id: `g${id}`,
  lat: null,
  lng: null,
  start,
  end,
  move_min: null,
  move_mode: null,
  hours: 'Google',
  hours_source: 'google_regular',
  locked: false,
  warnings: [],
})
const day = {
  date: '2030-12-28',
  start: '09:00',
  end: '21:00',
  depot: '숙소',
  back_at: '15:00',
  back_move_min: 20,
  warnings: [],
  items: [stop(1, '박물관', '10:00', '12:00'), stop(2, '시장', '13:00', '14:00')],
}
const fx = {
  base: 'JPY',
  quote: 'KRW',
  rate: 9.3,
  date: '2030-12-27',
  source: 'ECB 기준환율 (Frankfurter)',
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Today />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Today', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('shows the current and next stop by the trip clock, with directions and the yen calculator', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2030-12-28T01:30:00Z')) // 10:30 in Tokyo
    mockApi([
      [
        '/today',
        {
          phase: 'during',
          today: '2030-12-28',
          days_until: 0,
          itinerary_id: 5,
          day,
          weather: null,
          fx,
          weather_attribution: 'Weather data by Open-Meteo.com',
        },
      ],
      ['/api/trips', [trip]],
    ])
    renderPage()
    expect(await screen.findByText('지금 · 10:00~12:00')).toBeInTheDocument()
    expect(screen.getByText('다음 · 13:00~14:00')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Google 지도로 길찾기' })[0]).toHaveAttribute(
      'href',
      expect.stringContaining('destination_place_id=g1'),
    )
    expect(screen.getByText('9,300원')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('엔화 금액'), { target: { value: '2500' } })
    expect(screen.getByText('23,250원')).toBeInTheDocument()
  })

  it('counts down before the trip and previews the first day', async () => {
    mockApi([
      [
        '/today',
        {
          phase: 'before',
          today: '2030-12-20',
          days_until: 8,
          itinerary_id: 5,
          day,
          weather: null,
          fx: null,
          weather_attribution: 'Weather data by Open-Meteo.com',
        },
      ],
      ['/api/trips', [trip]],
    ])
    renderPage()
    expect(await screen.findByText('출발까지 D-8')).toBeInTheDocument()
    expect(screen.getByText(/첫날 미리보기/)).toBeInTheDocument()
    expect(screen.queryByText(/^지금 ·/)).not.toBeInTheDocument()
  })

  it('shows the saved plan with now and next when the home Mac cannot be reached', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2030-12-28T01:30:00Z')) // 10:30 in Tokyo
    const s = (seq: number, label: string, start: string, end: string) => ({
      seq,
      start,
      end,
      label,
      local_name: null,
      area: null,
      note: null,
      google_place_id: `g${seq}`,
      directions_url: `https://www.google.com/maps/dir/?api=1&destination=${seq}`,
      warnings: [],
    })
    await saveBundle({
      trip: {
        id: 1,
        title: '도쿄',
        timezone: 'Asia/Tokyo',
        start_date: '2030-12-28',
        end_date: '2030-12-29',
      },
      generated_at: '2030-12-27T00:00:00Z',
      itinerary_id: 5,
      version: 2,
      days: [
        {
          date: '2030-12-28',
          depot: '숙소',
          route_urls: [],
          stops: [s(1, '박물관', '10:00', '12:00'), s(2, '시장', '13:00', '14:00')],
        },
        {
          date: '2030-12-29',
          depot: '숙소',
          route_urls: [],
          stops: [s(3, '공원', '10:00', '11:00')],
        },
      ],
      checklist: [],
      bookings: { flights: [], stays: [], reservations: [] },
    })
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )
    renderPage()
    expect(await screen.findByText('오늘 · 저장된 일정')).toBeInTheDocument()
    expect(screen.getByText('지금 · 10:00~12:00')).toBeInTheDocument()
    expect(screen.getByText('다음 · 13:00~14:00')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: /12\/29/ }))
    expect(screen.getByText('공원')).toBeInTheDocument()
    expect(screen.queryByText(/^지금 ·/)).not.toBeInTheDocument()
    _clearMemory()
  })
})
