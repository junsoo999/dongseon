import { AdvancedMarker, APIProvider, Map, Polyline, useMap } from '@vis.gl/react-google-maps'
import { useEffect } from 'react'
import type { ItemOut } from '../api/client'
import { CATEGORY_EMOJI } from '../lib/places'

const KEY = import.meta.env.VITE_GOOGLE_MAPS_JS_KEY
const MAP_ID = import.meta.env.VITE_GOOGLE_MAP_ID

type Pt = { lat: number; lng: number }

function Fit({ points }: { points: Pt[] }) {
  const map = useMap()
  const sig = points.map((p) => `${p.lat},${p.lng}`).join('|')
  useEffect(() => {
    if (!map || points.length === 0) return
    if (points.length === 1) {
      map.setCenter(points[0])
      map.setZoom(14)
      return
    }
    const lats = points.map((p) => p.lat)
    const lngs = points.map((p) => p.lng)
    map.fitBounds(
      {
        north: Math.max(...lats),
        south: Math.min(...lats),
        east: Math.max(...lngs),
        west: Math.min(...lngs),
      },
      48,
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, sig])
  return null
}

/** One day's visits as numbered markers joined in order (straight dashed lines, not a route). */
export function DayMap({ items, center }: { items: ItemOut[]; center: Pt }) {
  if (!KEY || !MAP_ID) {
    return (
      <div className="flex h-full items-center justify-center bg-gray-100 p-4 text-center text-sm text-gray-500">
        지도를 보려면 .env에 VITE_GOOGLE_MAPS_JS_KEY와 VITE_GOOGLE_MAP_ID를 넣고 다시 빌드하세요.
      </div>
    )
  }
  const located = items.filter((i): i is ItemOut & Pt => i.lat !== null && i.lng !== null)
  const path = located.map((i) => ({ lat: i.lat, lng: i.lng }))
  return (
    <APIProvider apiKey={KEY} language="ko">
      <Map
        mapId={MAP_ID}
        defaultCenter={center}
        defaultZoom={12}
        gestureHandling="greedy"
        disableDefaultUI
        zoomControl
        clickableIcons={false}
        className="h-full w-full"
      >
        {path.length > 1 && (
          <Polyline
            path={path}
            strokeOpacity={0}
            icons={[
              {
                icon: { path: 'M 0,-1 0,1', strokeOpacity: 0.9, strokeColor: '#0f766e', scale: 3 },
                offset: '0',
                repeat: '12px',
              },
            ]}
          />
        )}
        {located.map((i, n) => (
          <AdvancedMarker
            key={i.id}
            position={{ lat: i.lat, lng: i.lng }}
            title={i.label}
            zIndex={100 - n}
          >
            <span className="flex items-center gap-1 rounded-full bg-white py-0.5 pr-2 pl-0.5 shadow-md ring-1 ring-black/5">
              <span className="flex size-6 items-center justify-center rounded-full bg-teal-700 text-xs font-bold text-white">
                {n + 1}
              </span>
              <span className="text-sm leading-none">
                {CATEGORY_EMOJI[i.category ?? ''] ?? '📍'}
              </span>
              <span className="max-w-24 truncate text-xs font-semibold text-gray-800">
                {i.label}
              </span>
            </span>
          </AdvancedMarker>
        ))}
        <Fit points={path} />
      </Map>
    </APIProvider>
  )
}
