import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AiSuggestions } from './AiSuggestions'

const suggestion = {
  id: 7,
  kind: 'place',
  status: 'pending',
  google_place_id: 'g1',
  lat: 35.67,
  lng: 139.77,
  created_at: '2026-11-05T00:00:00Z',
  stay: null,
  place: {
    name: '스시 가짜',
    name_local: '鮨偽',
    area: '긴자',
    category: 'food',
    meal: 'dinner',
    why: '스시를 좋아하는 일행에게',
    reservation: 'required',
    price_range: '¥20,000~',
    holiday_note: '12/31~1/3 휴무',
    sources: [{ title: '가이드', url: 'https://example.com/g' }],
    confidence: 'high',
  },
}

describe('AiSuggestions', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows sources and accepts a suggestion', async () => {
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      if (url.startsWith('/api/jobs'))
        return Promise.resolve(new Response(JSON.stringify({ running: false })))
      if (init?.method === 'POST')
        return Promise.resolve(new Response(JSON.stringify({ pin_id: 1, stay_id: null })))
      return Promise.resolve(
        new Response(
          JSON.stringify(
            [1, 2, 3, 4, 5].map((i) => ({ ...suggestion, id: i === 1 ? 7 : 100 + i })),
          ),
        ),
      )
    })
    vi.stubGlobal('fetch', fetchMock)
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <AiSuggestions tripId={1} kind="place" />
      </QueryClientProvider>,
    )
    expect((await screen.findAllByText('스시 가짜')).length).toBe(3)
    fireEvent.click(screen.getByRole('button', { name: '추천 2개 더 보기' }))
    expect(screen.getAllByText('스시 가짜')).toHaveLength(5)
    expect(screen.getAllByText(/긴자 · 식당 · 저녁 · 예약 필수 · ¥20,000~/)[0]).toBeInTheDocument()
    expect(screen.getAllByText('12/31~1/3 휴무')[0]).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: '가이드' })[0]).toHaveAttribute(
      'href',
      'https://example.com/g',
    )
    expect(screen.getByText('AI 제안')).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: '여행에 넣기' })[0])
    await vi.waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/suggestions/7/accept',
        expect.objectContaining({ method: 'POST' }),
      ),
    )
  })
})
