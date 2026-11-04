import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/mockApi'
import { LiveFares, LiveHotels } from './LivePrices'

const fare = (id: number, over: object) => ({
  id,
  route: 'ICN-NRT',
  amount: 775004,
  currency: 'KRW',
  total_krw: 775004,
  usable_min: 5914,
  krw_per_usable_hour: 7863,
  best_value: false,
  cheapest: false,
  legs: [
    {
      direction: 'out',
      flight: 'RS247',
      carrier_code: 'RS',
      duration_min: 135,
      carrier: '에어서울',
      dep_airport: 'ICN',
      dep_local: '2026-12-28T08:10',
      arr_airport: 'NRT',
      arr_local: '2026-12-28T10:25',
    },
    {
      direction: 'back',
      flight: '7C1108',
      carrier_code: '7C',
      duration_min: 180,
      carrier: '제주항공',
      dep_airport: 'NRT',
      dep_local: '2027-01-01T18:15',
      arr_airport: 'ICN',
      arr_local: '2027-01-01T21:15',
    },
  ],
  ...over,
})

function wrap(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>)
}

describe('LivePrices', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows fares with badges and adds one', async () => {
    const fetchMock = mockApi([
      [
        '/fares',
        {
          fetched_at: '2026-11-05T01:00:00Z',
          reference_label: '신주쿠',
          reference_kind: 'first_area',
          items: [
            fare(1, { best_value: true, amount: 779804, total_krw: 779804 }),
            fare(2, { cheapest: true }),
          ],
        },
      ],
    ])
    wrap(<LiveFares tripId={1} />)
    expect(await screen.findByText('가성비 1위')).toBeInTheDocument()
    expect(screen.getByText('최저가')).toBeInTheDocument()
    expect(screen.getAllByText(/12\/28\(월\) · 에어서울 RS247/)).toHaveLength(2)
    expect(screen.getAllByText('2시간 15분')).toHaveLength(2)
    expect(screen.getAllByAltText('에어서울')[0]).toHaveAttribute(
      'src',
      expect.stringContaining('/RS@png'),
    )
    expect(screen.getAllByText(/1시간당 ₩7,863/)).toHaveLength(2)
    expect(screen.getByText(/신주쿠 기준 근사/)).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: '후보로 추가' })[0])
    await vi.waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/trips/1/fares/1/add',
        expect.objectContaining({ method: 'POST' }),
      ),
    )
  })

  it('shows Rakuten vacancies with credit', async () => {
    mockApi([
      [
        '/hotels',
        {
          fetched_at: '2026-11-05T01:00:00Z',
          check_in: '2026-12-28',
          check_out: '2027-01-01',
          credit_text: 'Supported by Rakuten Developers',
          credit_url: 'https://developers.rakuten.com/',
          areas: [
            {
              area: '긴자',
              emoji: '💎',
              items: [
                {
                  id: 3,
                  name: 'BAN HOTEL 築地銀座',
                  nearest_station: '築地',
                  review_average: 4.21,
                  review_count: 120,
                  thumbnail_url: null,
                  info_url: null,
                  room_name: 'ダブル',
                  nightly_jpy: 17860,
                  nightly_krw: 151072,
                  bath_hint: true,
                  reserve_url: 'https://travel.rakuten.co.jp/x',
                },
              ],
            },
          ],
        },
      ],
    ])
    wrap(<LiveHotels tripId={1} />)
    expect(await screen.findByText('BAN HOTEL 築地銀座')).toBeInTheDocument()
    expect(screen.getByText('₩151,072')).toBeInTheDocument()
    expect(screen.getByText('욕조 언급')).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Supported by Rakuten Developers' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '楽天トラベル에서 보기' })).toHaveAttribute(
      'href',
      'https://travel.rakuten.co.jp/x',
    )
  })
})
