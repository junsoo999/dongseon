import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/mockApi'
import { Places } from './Places'

// The real map needs a browser key and the Google loader; tests check the page around it.
vi.mock('../components/PlacesMap', () => ({
  PlacesMap: ({ pins }: { pins: unknown[] }) => <div>지도 핀 {pins.length}개</div>,
}))

const trip = {
  id: 1,
  title: '도쿄 테스트',
  city_key: 'tokyo',
  city_name: '도쿄',
  start_date: '2030-12-28',
  end_date: '2031-01-01',
  timezone: 'Asia/Tokyo',
  pace: 'normal',
  status: 'planning',
  pin_count: 2,
  center_lat: 35.681,
  center_lng: 139.767,
}

const basePin = {
  place_id: 1,
  user_note: null,
  tag: null,
  source: 'search',
  dwell_min: 60,
  meal: null,
  locked_date: null,
  note: null,
  added_by: 'user',
}

const pins = [
  {
    ...basePin,
    id: 1,
    google_place_id: 'g1',
    label: '여유 카페',
    category: 'cafe',
    resolve_status: 'ok',
    priority: 'maybe',
    lat: 35.6,
    lng: 139.7,
  },
  {
    ...basePin,
    id: 2,
    google_place_id: null,
    label: '꼭 가는 곳',
    category: 'other',
    resolve_status: 'pending',
    priority: 'must',
    lat: null,
    lng: null,
    meal: 'lunch',
  },
]

function renderPage() {
  mockApi([
    ['/api/trips/1/pins', pins],
    ['/suggestions', []],
    ['/api/trips', [trip]],
  ])
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Places />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Places', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('lists pins must-first and flags unmatched places', async () => {
    renderPage()
    expect(await screen.findByText('도쿄 테스트')).toBeInTheDocument()
    const items = await screen.findAllByRole('listitem')
    expect(items[0]).toHaveTextContent('꼭 가는 곳')
    expect(items[0]).toHaveTextContent('점심')
    expect(within(items[0]).getByText('미연결')).toBeInTheDocument()
    expect(items[1]).toHaveTextContent('여유 카페')
    expect(screen.getByText(/연결되지 않은 곳이 1곳/)).toBeInTheDocument()
    expect(screen.getByText('지도 핀 2개')).toBeInTheDocument()
  })

  it('filters by priority from the filter sheet', async () => {
    renderPage()
    await screen.findAllByRole('listitem')
    fireEvent.click(screen.getByRole('button', { name: '필터' }))
    fireEvent.click(screen.getByRole('button', { name: '꼭' }))
    expect(screen.getByText(/1곳 표시/)).toBeInTheDocument()
    expect(screen.getByText('지도 핀 1개')).toBeInTheDocument()
  })
})
