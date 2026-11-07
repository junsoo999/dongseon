import { Component, type ReactNode } from 'react'

/**
 * Keeps a Google Maps failure (billing, key or referrer problems make marker code throw) inside the map area,
 * so the list beside it stays usable.
 */
export class MapBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div className="flex h-full min-h-48 flex-col items-center justify-center gap-2 bg-gray-100 p-4 text-center text-sm text-gray-600">
        <p>지도를 불러오지 못했습니다. 목록과 길찾기는 그대로 쓸 수 있습니다.</p>
        <button
          type="button"
          onClick={() => this.setState({ failed: false })}
          className="min-h-11 rounded-xl px-4 font-medium text-teal-700 hover:bg-teal-50"
        >
          지도 다시 시도
        </button>
      </div>
    )
  }
}
