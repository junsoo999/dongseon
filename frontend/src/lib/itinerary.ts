import type { ItemOut } from '../api/client'

/** Google Maps directions to a stop by public transit from wherever the phone is (Maps URLs, no key). */
export function directionsUrl(
  item: Pick<ItemOut, 'label' | 'google_place_id'>,
  mode: 'transit' | 'walking' = 'transit',
): string {
  const q = new URLSearchParams({ api: '1', destination: item.label, travelmode: mode })
  if (item.google_place_id) q.set('destination_place_id', item.google_place_id)
  return `https://www.google.com/maps/dir/?${q.toString()}`
}

export const MOVE_ICON: Record<string, string> = { walk: '🚶', rail: '🚃' }

/** "1시간 05분 이동" style label for a move. */
export function moveLabel(
  min: number | null | undefined,
  mode: string | null | undefined,
): string | null {
  if (!min) return null
  return `${MOVE_ICON[mode ?? ''] ?? '➡️'} ${min}분${mode === 'rail' ? ' (근사)' : ''}`
}
