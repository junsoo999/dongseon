import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MapBoundary } from './MapBoundary'

function Broken(): never {
  throw new TypeError("Cannot read properties of undefined (reading 'keys')")
}

describe('MapBoundary', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('keeps a map failure inside the map area', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <div>
        <MapBoundary>
          <Broken />
        </MapBoundary>
        <p>일정 목록</p>
      </div>,
    )
    expect(screen.getByText(/지도를 불러오지 못했습니다/)).toBeInTheDocument()
    expect(screen.getByText('일정 목록')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '지도 다시 시도' }))
    expect(screen.getByText(/지도를 불러오지 못했습니다/)).toBeInTheDocument() // still broken, still contained
  })
})
