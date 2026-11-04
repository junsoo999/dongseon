import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/mockApi'
import { Itinerary } from './Itinerary'

vi.mock('../components/DayMap', () => ({
  DayMap: ({ items }: { items: unknown[] }) => <div>지도 {items.length}곳</div>,
}))

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
  center_lat: 35.681,
  center_lng: 139.767,
}
const item = {
  id: 10,
  pin_id: 1,
  label: '박물관',
  kind: 'visit',
  category: 'museum',
  priority: 'must',
  google_place_id: 'g1',
  lat: 35.7,
  lng: 139.77,
  start: '10:00',
  end: '12:00',
  move_min: 25,
  move_mode: 'rail',
  hours: '10:00~18:00 · Google',
  warnings: ['연휴 기간 영업 미확인'],
}
const itinerary = {
  id: 5,
  version: 2,
  origin: 'solver',
  status: 'active',
  created_at: '2026-11-05T00:00:00Z',
  approx: true,
  days: [
    {
      date: '2030-12-28',
      start: '13:00',
      end: '21:00',
      depot: '숙소',
      back_at: '20:30',
      back_move_min: 20,
      warnings: ['점심 일정이 없습니다'],
      items: [item],
    },
    {
      date: '2030-12-29',
      start: '09:00',
      end: '21:00',
      depot: '숙소',
      back_at: null,
      back_move_min: null,
      warnings: [],
      items: [],
    },
  ],
  dropped: [
    { pin_id: 2, label: '먼 곳', priority: 'maybe', reason: '하루 시간 안에 넣지 못했습니다' },
  ],
}

describe('Itinerary', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows the day timeline with hours, warnings, directions and dropped pins', async () => {
    mockApi([
      ['/itineraries/active', itinerary],
      ['/api/trips', [trip]],
    ])
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <Itinerary />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByText('박물관')).toBeInTheDocument()
    expect(screen.getByText('🕘 10:00~18:00 · Google')).toBeInTheDocument()
    expect(screen.getByText('⚠️ 연휴 기간 영업 미확인')).toBeInTheDocument()
    expect(screen.getByText('⚠️ 점심 일정이 없습니다')).toBeInTheDocument()
    expect(screen.getByText('🚃 25분 (근사)')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '길찾기 ↗' })).toHaveAttribute(
      'href',
      expect.stringContaining('destination_place_id=g1'),
    )
    expect(screen.getByText('넣지 못한 곳 1곳')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '다시 만들기' })).toBeInTheDocument()
    expect(screen.getByText('지도 1곳')).toBeInTheDocument()
  })
})
