import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/mockApi'
import { Flights } from './Flights'

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

const leg = (direction: string, dep: string, depLocal: string, arr: string, arrLocal: string) => ({
  direction,
  carrier: null,
  flight_no: 'KE703',
  dep_airport: dep,
  dep_local: depLocal,
  dep_timezone: 'Asia/Seoul',
  arr_airport: arr,
  arr_local: arrLocal,
  arr_timezone: 'Asia/Tokyo',
  duration_min: 140,
})

const evaluation = (usable: number) => ({
  arrival_airport: 'NRT',
  arrival_local: '2030-12-28T11:20',
  ready_local: '2030-12-28T13:20',
  departure_airport: 'HND',
  departure_local: '2031-01-01T18:00',
  leave_by_local: '2031-01-01T15:15',
  access_in_min: 60,
  access_out_min: 45,
  immigration_buffer_min: 60,
  departure_buffer_min: 120,
  usable_min: usable,
  reference_label: '긴자',
  reference_kind: 'top_area',
  total_krw: 700000,
  krw_per_usable_hour: 7000,
  warnings: [],
})

const base = {
  currency: 'KRW',
  baggage_note: '23kg 1개',
  booking_url: null,
  note: null,
  status: 'candidate',
  problems: [],
}
const flights = [
  {
    ...base,
    id: 1,
    label: '아침 출발',
    total_amount: 700000,
    legs: [leg('out', 'ICN', '2030-12-28T09:00', 'NRT', '2030-12-28T11:20')],
    evaluation: evaluation(5875),
  },
  {
    ...base,
    id: 2,
    label: '저녁 출발',
    total_amount: 500000,
    legs: [],
    evaluation: evaluation(5000),
    problems: ['NRT에 도착한 뒤 KIX에서 출발합니다'],
  },
]

describe('Flights', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('compares usable time and marks the best option', async () => {
    mockApi([
      [
        '/search-links',
        {
          flights: [
            { site: 'naver', label: '네이버 항공권 ICN→TYO', url: 'https://flight.naver.com/x' },
          ],
          stays: [],
        },
      ],
      ['/flights', flights],
      ['/api/trips', [trip]],
    ])
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <Flights />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByText('4일 1시간 55분')).toBeInTheDocument()
    expect(screen.getByText('현지 시간 최다')).toBeInTheDocument()
    expect(screen.getByText(/12\/28\(토\) · KE703/)).toBeInTheDocument()
    expect(screen.getByText('09:00')).toBeInTheDocument()
    expect(screen.getAllByText(/1위 동네 긴자 기준/)).toHaveLength(2)
    expect(screen.getByText('NRT에 도착한 뒤 KIX에서 출발합니다')).toBeInTheDocument()
    expect(screen.getByText('현지에서 쓰는 시간')).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: /네이버 항공권/ })).toBeInTheDocument()
  })

  it('reads a pasted booking email and opens the flight form pre-filled', async () => {
    const fetch = mockApi([
      [
        '/parse-booking',
        {
          kind: 'flight',
          flight: {
            label: '대한항공 KE703',
            total_amount: 512000,
            currency: 'KRW',
            baggage_note: '23kg 1개',
            legs: [
              {
                direction: 'out',
                carrier: '대한항공',
                flight_no: 'KE703',
                dep_airport: 'ICN',
                dep_local: '2030-12-28T09:00:00',
                arr_airport: 'NRT',
                arr_local: '2030-12-28T11:30:00',
              },
            ],
          },
          stay: null,
          note: '오는 편이 없습니다',
          masked: { 카드번호: 1 },
        },
      ],
      ['/airports', [{ code: 'ICN', name: '인천', timezone: 'Asia/Seoul' }]],
      ['/flights', []],
      ['/api/trips', [trip]],
    ])
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <Flights />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    fireEvent.click(await screen.findByRole('button', { name: '📋 예약 메일로 입력' }))
    fireEvent.change(screen.getByLabelText('예약 메일 내용'), {
      target: { value: '대한항공 예약 확인 KE703 2030-12-28 09:00 인천 출발' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'AI로 읽기' }))
    expect(await screen.findByText(/항공편 1구간을 찾았습니다/)).toBeInTheDocument()
    expect(screen.getByText('⚠ 오는 편이 없습니다')).toBeInTheDocument()
    expect(screen.getByText('가린 정보: 카드번호 1개')).toBeInTheDocument()
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith('/api/trips/1/parse-booking', expect.anything()),
    )
    fireEvent.click(screen.getByRole('button', { name: '항공편 입력에서 확인하기' }))
    expect(await screen.findByDisplayValue('대한항공 KE703')).toBeInTheDocument()
    expect(screen.getByDisplayValue('KE703')).toBeInTheDocument()
    expect(screen.getByDisplayValue('512000')).toBeInTheDocument()
  })
})
