import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { OfflineOut } from '../api/client'
import { _clearMemory, saveBundle } from '../lib/offline'
import { mockApi } from '../test/mockApi'
import { Prep } from './Prep'

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
const item = (id: number, text: string, done = false) => ({
  id,
  section: '서류·입국',
  text,
  url: id === 1 ? 'https://example.org/' : null,
  done,
  sort: id,
})
const bookings = {
  flights: [
    {
      id: 1,
      label: '대한항공',
      total_amount: 500000,
      currency: 'KRW',
      baggage_note: null,
      booking_url: null,
      note: null,
      legs: [
        {
          direction: 'out',
          carrier: 'KE',
          flight_no: 'KE001',
          dep_airport: 'ICN',
          dep_local: '2030-12-28T09:00',
          arr_airport: 'NRT',
          arr_local: '2030-12-28T11:20',
        },
      ],
    },
  ],
  stays: [],
  reservations: [],
}
const offline: OfflineOut = {
  trip: {
    id: 1,
    title: '도쿄',
    timezone: 'Asia/Tokyo',
    start_date: '2030-12-28',
    end_date: '2030-12-29',
  },
  generated_at: '2030-12-27T00:00:00Z',
  itinerary_id: 7,
  version: 3,
  days: [
    {
      date: '2030-12-28',
      depot: '숙소',
      route_urls: ['https://www.google.com/maps/dir/?api=1&destination=a'],
      stops: [
        {
          seq: 1,
          start: '10:00',
          end: '12:00',
          label: '박물관',
          local_name: null,
          area: null,
          note: null,
          google_place_id: 'g1',
          directions_url: 'https://www.google.com/maps/dir/?api=1&destination=%EB%B0%95',
          warnings: [],
        },
      ],
    },
  ],
  checklist: [item(1, '여권 확인', true)],
  bookings,
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Prep />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Prep', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    _clearMemory()
  })

  it('seeds the checklist from the template', async () => {
    const fetch = mockApi([['/api/trips', [trip]]])
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: '기본 항목 채우기' }))
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        '/api/trips/1/checklist/seed',
        expect.objectContaining({ method: 'POST' }),
      ),
    )
  })

  it('checks items, shows bookings and the export links of the active version', async () => {
    const fetch = mockApi([
      [
        '/checklist',
        { items: [item(1, '여권 확인'), item(2, '보험')], template_as_of: '2026-11-08' },
      ],
      ['/bookings', bookings],
      ['/offline', offline],
      ['/api/trips', [trip]],
    ])
    renderPage()
    expect(await screen.findByText('0/2 완료')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('checkbox', { name: '여권 확인' }))
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        '/api/checklist/1',
        expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ done: true }) }),
      ),
    )
    expect(screen.getByRole('link', { name: '공식 안내' })).toHaveAttribute(
      'href',
      'https://example.org/',
    )
    expect(screen.getByText(/ICN 12\/28 09:00 → NRT 12\/28 11:20/)).toBeInTheDocument()
    expect(
      await screen.findByRole('link', { name: 'Google 내 지도용 CSV (날짜별 zip)' }),
    ).toHaveAttribute('href', '/api/itineraries/7/mymaps.zip')
    expect(screen.getByRole('link', { name: '캘린더 (ICS)' })).toHaveAttribute(
      'href',
      '/api/itineraries/7/export.ics',
    )
    expect(screen.getByRole('link', { name: '경로' })).toBeInTheDocument()
  })

  it('applies AI local names: all verified at once, or one by one', async () => {
    const s = (id: number, label: string, name: string, verified: boolean) => ({
      id,
      pin_id: id,
      label,
      name_local: name,
      sources: [{ title: '공식', url: 'https://example.org/' }],
      confidence: 'high',
      verified,
      created_at: '2030-12-01T00:00:00Z',
    })
    const fetch = mockApi([
      [
        '/local-names',
        {
          total: 3,
          filled: 0,
          suggestions: [s(1, '박물관', 'テスト博物館', true), s(2, '시장', 'テスト市場', false)],
        },
      ],
      ['/offline', offline],
      ['/api/trips', [trip]],
    ])
    renderPage()
    expect(await screen.findByText(/현지 이름 0\/3곳/)).toBeInTheDocument()
    expect(screen.getByText('확인 필요 (검색에 이 장소가 안 나옴)')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'AI로 채우기' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '확인된 1곳 모두 적용' }))
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        '/api/trips/1/local-names/accept-verified',
        expect.objectContaining({ method: 'POST' }),
      ),
    )
    fireEvent.click(screen.getAllByRole('button', { name: '아니에요' })[1])
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        '/api/local-names/2/reject',
        expect.objectContaining({ method: 'POST' }),
      ),
    )
  })

  it('reads the saved copy when the server cannot be reached', async () => {
    await saveBundle(offline)
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )
    renderPage()
    expect(await screen.findByText('준비 · 저장된 내용')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: '여권 확인' })).toBeDisabled()
    expect(screen.getByText('✈️ 대한항공')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '기본 항목 채우기' })).not.toBeInTheDocument()
  })
})
