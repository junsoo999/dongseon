import { AdvancedMarker, APIProvider, Map, useMap } from '@vis.gl/react-google-maps'
import { useEffect } from 'react'
import type { OriginOut, PinOut } from '../api/client'
import { rankColor } from '../lib/stays'

const KEY = import.meta.env.VITE_GOOGLE_MAPS_JS_KEY
const MAP_ID = import.meta.env.VITE_GOOGLE_MAP_ID

type Point = { lat: number; lng: number }

function FitTo({ points }: { points: Point[] }) {
  const map = useMap()
  const signature = points.map((p) => `${p.lat.toFixed(4)},${p.lng.toFixed(4)}`).join('|')
  useEffect(() => {
    if (!map || points.length < 2) return
    const lats = points.map((p) => p.lat)
    const lngs = points.map((p) => p.lng)
    map.fitBounds(
      {
        north: Math.max(...lats),
        south: Math.min(...lats),
        east: Math.max(...lngs),
        west: Math.min(...lngs),
      },
      40,
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, signature])
  return null
}

export function StaysMap({
  origins,
  pins,
  center,
  onSelect,
}: {
  origins: OriginOut[]
  pins: PinOut[]
  center: Point
  onSelect: (id: string) => void
}) {
  if (!KEY || !MAP_ID) {
    return (
      <div className="flex h-full items-center justify-center bg-gray-100 p-4 text-center text-sm text-gray-500">
        지도를 보려면 .env에 VITE_GOOGLE_MAPS_JS_KEY와 VITE_GOOGLE_MAP_ID를 넣고 다시 빌드하세요.
      </div>
    )
  }
  const located = origins.filter((o): o is OriginOut & Point => o.lat !== null && o.lng !== null)
  const ranked = located.filter((o) => o.rank !== null).length
  const targets = pins.filter(
    (p): p is PinOut & Point =>
      p.lat !== null && p.lng !== null && (p.priority === 'must' || p.priority === 'want'),
  )
  return (
    <APIProvider apiKey={KEY} language="ko">
      <Map
        mapId={MAP_ID}
        defaultCenter={center}
        defaultZoom={11}
        gestureHandling="greedy"
        disableDefaultUI
        zoomControl
        clickableIcons={false}
        className="h-full w-full"
      >
        {targets.map((p) => (
          <AdvancedMarker key={`pin-${p.id}`} position={{ lat: p.lat, lng: p.lng }} title={p.label}>
            <span className="block size-2.5 rounded-full border border-white bg-gray-700/70" />
          </AdvancedMarker>
        ))}
        {located.map((o) => (
          <AdvancedMarker
            key={o.id}
            position={{ lat: o.lat, lng: o.lng }}
            title={o.label}
            onClick={() => onSelect(o.id)}
            zIndex={o.rank !== null ? 100 - o.rank : 0}
          >
            <span
              className={`flex h-7 min-w-7 items-center justify-center px-1.5 text-xs font-bold text-white shadow ${o.kind === 'stay' ? 'rounded-md' : 'rounded-full'}`}
              style={{ background: rankColor(o.rank, ranked) }}
            >
              {o.rank ?? '–'}
            </span>
          </AdvancedMarker>
        ))}
        <FitTo points={[...located, ...targets]} />
      </Map>
    </APIProvider>
  )
}

/** A map where tapping sets a point (for stays without a Google place, e.g. an Airbnb's rough location). */
export function PickPointMap({
  center,
  value,
  onChange,
}: {
  center: Point
  value: Point | null
  onChange: (p: Point) => void
}) {
  if (!KEY || !MAP_ID)
    return <p className="text-sm text-gray-500">지도 키가 없어 위치를 찍을 수 없습니다.</p>
  return (
    <APIProvider apiKey={KEY} language="ko">
      <Map
        mapId={MAP_ID}
        defaultCenter={value ?? center}
        defaultZoom={13}
        gestureHandling="greedy"
        disableDefaultUI
        zoomControl
        clickableIcons={false}
        className="h-64 w-full rounded-lg"
        onClick={(e) => {
          const ll = e.detail.latLng
          if (ll) onChange({ lat: ll.lat, lng: ll.lng })
        }}
      >
        {value && <AdvancedMarker position={value} />}
      </Map>
    </APIProvider>
  )
}
