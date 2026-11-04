import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { HealthBadge } from './HealthBadge'

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <HealthBadge />
    </QueryClientProvider>,
  )
}

describe('HealthBadge', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows ok when backend responds', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            status: 'ok',
            version: '0.1.0',
            last_daily_at: null,
            database_exists: false,
            profile_loaded: true,
            keys: {},
          }),
        ),
      ),
    )
    renderWithClient()
    expect(await screen.findByText(/백엔드 정상/)).toBeInTheDocument()
  })

  it('shows failure when backend is down', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 502 })))
    renderWithClient()
    expect(await screen.findByText('백엔드 연결 실패')).toBeInTheDocument()
  })
})
