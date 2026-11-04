import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Stays } from './Stays'

vi.mock('../components/StaysMap', () => ({
  StaysMap: ({ origins }: { origins: unknown[] }) => <div>지도 후보 {origins.length}곳</div>,
  PickPointMap: () => <div />,
}))

const trip = {
  id: 1,
  title: '도쿄',
  city_key: 'tokyo',
  city_name: '도쿄',
  start_date: '2030-12-28',
  end_date: '2031-01-01',
  timezone: 'Asia/Tokyo',
  pace: 'normal',
  status: 'planning',
  pin_count: 1,
  center_lat: 35.681,
  center_lng: 139.767,
}

const origin = {
  lat: 35.6,
  lng: 139.7,
  max_min: 30,
  farthest_label: '먼 곳',
  airport_min: { HND: 45, NRT: 65 },
  nightly_krw: null,
}

const score = {
  targets: 3,
  targets_without_coords: 0,
  weights: { must: 100, want: 10 },
  approx_as_of: '2026-11-05',
  approx_source_url: 'https://example.com',
  airport_notes: { NRT: '스카이라이너 (닛포리에서 최단 36분)' },
  fx: [
    {
      base: 'JPY',
      quote: 'KRW',
      rate: 8.4587,
      date: '2026-11-04',
      source: 'ECB 기준환율 (Frankfurter)',
    },
  ],
  origins: [
    { ...origin, kind: 'area', id: 'area:긴자', label: '긴자', weighted_avg_min: 22, rank: 1 },
    {
      ...origin,
      kind: 'stay',
      id: 'stay:5',
      label: '에어비앤비',
      weighted_avg_min: 25,
      rank: 2,
      nightly_krw: 253761,
    },
  ],
}

const stays = [
  {
    id: 5,
    label: '에어비앤비',
    google_place_id: null,
    lat: 35.6,
    lng: 139.7,
    location_source: 'user',
    check_in: '2030-12-28',
    check_out: '2031-01-01',
    nights: 4,
    total_amount: 120000,
    currency: 'JPY',
    nightly_amount: 30000,
    nightly_krw: 253761,
    booking_url: 'https://www.airbnb.com/rooms/1',
    note: null,
    status: 'candidate',
  },
]

describe('Stays', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('ranks areas and stays with airport times and nightly price', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        const body = url.includes('/stays/score')
          ? score
          : url.includes('/stays')
            ? stays
            : url.includes('/pins')
              ? []
              : [trip]
        return Promise.resolve(new Response(JSON.stringify(body)))
      }),
    )
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <Stays />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByText('긴자')).toBeInTheDocument()
    expect(screen.getAllByText(/하네다 45분 · 나리타 1시간 5분/)).toHaveLength(2)
    expect(screen.getByText('₩253,761')).toBeInTheDocument()
    expect(screen.getByText(/4박/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '예약 페이지' })).toHaveAttribute(
      'href',
      'https://www.airbnb.com/rooms/1',
    )
    expect(screen.getByText(/스카이라이너/)).toBeInTheDocument()
    expect(screen.getByText(/1 JPY = 8.4587 KRW .*2026-11-04 기준/)).toBeInTheDocument()
    expect(screen.getByText('지도 후보 2곳')).toBeInTheDocument()
  })
})
