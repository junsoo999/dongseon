import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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
  hours_source: 'google_regular',
  locked: false,
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
    {
      pin_id: 2,
      label: '먼 곳',
      priority: 'maybe',
      reason: '하루 시간 안에 넣지 못했습니다',
      excluded: false,
    },
  ],
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Itinerary />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Itinerary', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('edits a layout: moving a visit to another day locks it and saves a new version', async () => {
    const fetch = mockApi([
      ['/edit', { ...itinerary, id: 6, version: 3, origin: 'user' }],
      ['/itineraries/active', itinerary],
      ['/api/trips', [trip]],
    ])
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: '✏️ 편집' }))
    expect(screen.getByText('편집 중')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '저장' })).toBeDisabled()
    fireEvent.change(screen.getByLabelText('다른 날로 옮기기'), {
      target: { value: '2030-12-29' },
    })
    expect(
      screen.getByText('이 날은 비어 있습니다. 아래에서 넣을 수 있습니다.'),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '저장' }))
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith('/api/itineraries/5/edit', expect.anything()),
    )
    const call = fetch.mock.calls.find(([url]) => url === '/api/itineraries/5/edit')
    expect(JSON.parse(call?.[1]?.body as string)).toEqual({
      days: [
        { date: '2030-12-28', pin_ids: [] },
        { date: '2030-12-29', pin_ids: [1] },
      ],
      locked: [1],
      excluded: [],
      resolve: false,
    })
    expect(await screen.findByRole('button', { name: '버전 3 ▾' })).toBeInTheDocument()
  })

  it('shows the day timeline with hours, warnings, directions and dropped pins', async () => {
    mockApi([
      ['/itineraries/active', itinerary],
      ['/api/trips', [trip]],
    ])
    renderPage()
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
    expect(screen.getByRole('button', { name: '다시 맞추기' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '버전 2 ▾' })).toBeInTheDocument()
    expect(screen.getByText('지도 1곳')).toBeInTheDocument()
  })

  it('shows weather per day, highlights a rainy day and the changed-hours alert', async () => {
    const fetch = mockApi([
      [
        '/weather',
        {
          days: [
            {
              date: '2030-12-28',
              kind: 'forecast',
              code: 61,
              tmax: 11.2,
              tmin: 3.8,
              precip_mm: 5,
              precip_prob: 80,
              rainy: true,
              years: null,
              fetched_at: '2030-12-27T00:00:00Z',
            },
          ],
          rain_probability_pct: 60,
          attribution: 'Weather data by Open-Meteo.com',
          attribution_url: 'https://open-meteo.com/',
        },
      ],
      ['/alerts/3/dismiss', null],
      [
        '/alerts',
        [
          {
            id: 3,
            kind: 'hours_changed',
            itinerary_id: 5,
            added: ['박물관: 이 날은 휴무입니다'],
            resolved: [],
            created_at: '2030-12-21T00:00:00Z',
          },
        ],
      ],
      ['/itineraries/active', itinerary],
      ['/api/trips', [trip]],
    ])
    renderPage()
    expect(await screen.findByText('🌧️ 비 · 4°/11° · 강수 80%')).toBeInTheDocument()
    expect(screen.getByText('Weather data by Open-Meteo.com')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '☔ 비 예보 · 대안 만들기' })).toBeInTheDocument()
    expect(await screen.findByText('⚠️ 박물관: 이 날은 휴무입니다')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '닫기' }))
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith('/api/alerts/3/dismiss', expect.anything()),
    )
  })

  it('shows AI review notes and edits, previews one and accepts it as a new version', async () => {
    const edit = (id: number, applicable: boolean, extra = {}) => ({
      id,
      source: 'review',
      date: null,
      itinerary_version: 2,
      op: 'move',
      title: `제안 ${id}`,
      reason: '가까운 곳끼리 묶습니다',
      applicable,
      problems: applicable ? [] : ['박물관: 이 날은 휴무입니다'],
      created_at: '2026-11-07T00:00:00Z',
      ...extra,
    })
    const moved = {
      ...itinerary,
      id: 0,
      days: [
        { ...itinerary.days[0], items: [] },
        { ...itinerary.days[1], items: [{ ...item, start: '09:30', end: '11:30' }] },
      ],
    }
    const fetch = mockApi([
      [
        '/plan-suggestions/31/preview',
        { itinerary: moved, applicable: true, problems: [], resolved: false },
      ],
      ['/plan-suggestions/31/accept', { ...itinerary, id: 7, version: 3, origin: 'ai' }],
      [
        '/plan-suggestions',
        {
          reviews: [
            {
              id: 30,
              source: 'review',
              date: null,
              itinerary_version: 2,
              day_titles: [{ date: '2030-12-28', title: '우에노 산책' }],
              notes: ['연말에는 붐빕니다'],
              created_at: '2026-11-07T00:00:00Z',
            },
          ],
          edits: [
            edit(32, false),
            edit(31, true),
            edit(33, true, { source: 'rain', date: '2030-12-28', title: '비 오면 실내로' }),
          ],
        },
      ],
      ['/itineraries/active', itinerary],
      ['/api/trips', [trip]],
    ])
    renderPage()
    expect(await screen.findByText('💡 연말에는 붐빕니다')).toBeInTheDocument()
    expect(screen.getByText(/우에노 산책/)).toBeInTheDocument()
    expect(screen.getByText('고칠 점 3개 · 적용 가능 2개')).toBeInTheDocument()
    expect(screen.getByText('⚠ 박물관: 이 날은 휴무입니다')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '☔ 비 오면? · 대안 1' })).toBeInTheDocument()

    const card = screen.getByText('제안 31').closest('li') as HTMLElement
    fireEvent.click(within(card).getByRole('button', { name: '미리보기' }))
    expect(await screen.findByText('12/28 → 12/29 이동 (09:30)')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '수락하고 새 버전 만들기' }))
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith('/api/plan-suggestions/31/accept', expect.anything()),
    )
    expect(await screen.findByRole('button', { name: '버전 3 ▾' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '☔ 비 오면? · 대안 1' }))
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith('/api/itineraries/7/review', expect.anything()),
    )
    const call = fetch.mock.calls.find(([url]) => url === '/api/itineraries/7/review')
    expect(JSON.parse(call?.[1]?.body as string)).toEqual({ rain_date: '2030-12-28', force: true })
  })

  it('shows holiday hours research with sources and the AI hours link on a visit', async () => {
    const aiItem = {
      ...item,
      hours: '10:00~16:00 · AI 조사',
      hours_source: 'ai_research',
      hours_url: 'https://example.com/hours',
    }
    mockApi([
      [
        '/hours-research',
        {
          dates: ['2030-12-29'],
          holiday_note: '연말연시',
          places: [
            {
              pin_id: 1,
              label: '박물관',
              priority: 'must',
              days: [
                {
                  date: '2030-12-29',
                  status: 'closed',
                  open: null,
                  close: null,
                  source_url: 'https://example.com/hours',
                  checked_at: '2026-11-07T00:00:00Z',
                },
              ],
            },
          ],
        },
      ],
      [
        '/itineraries/active',
        { ...itinerary, days: [{ ...itinerary.days[0], items: [aiItem] }, itinerary.days[1]] },
      ],
      ['/api/trips', [trip]],
    ])
    renderPage()
    expect(await screen.findByText('연휴 영업시간 조사')).toBeInTheDocument()
    expect(screen.getByText(/꼭·가고 싶은 곳 1곳 중 1곳 확인/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '조사 결과 보기' }))
    expect(screen.getByRole('link', { name: '12/29 휴무 ↗' })).toHaveAttribute(
      'href',
      'https://example.com/hours',
    )
    expect(screen.getByText('확인 필요')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '출처↗' })).toHaveAttribute(
      'href',
      'https://example.com/hours',
    )
  })
})
