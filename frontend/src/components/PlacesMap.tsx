import { AdvancedMarker, APIProvider, Map, Pin, useMap } from '@vis.gl/react-google-maps'
import { useEffect } from 'react'
import type { PinOut } from '../api/client'
import { isPriority, PRIORITY_COLORS } from '../lib/places'

const KEY = import.meta.env.VITE_GOOGLE_MAPS_JS_KEY
const MAP_ID = import.meta.env.VITE_GOOGLE_MAP_ID

type Located = PinOut & { lat: number; lng: number }

function located(pins: PinOut[]): Located[] {
  return pins.filter((p): p is Located => p.lat !== null && p.lng !== null)
}

/** Fit the map to the pins whenever the set of pins changes. */
function FitToPins({ pins }: { pins: Located[] }) {
  const map = useMap()
  const signature = pins.map((p) => p.id).join(',')
  useEffect(() => {
    if (!map || pins.length === 0) return
    if (pins.length === 1) {
      map.setCenter({ lat: pins[0].lat, lng: pins[0].lng })
      map.setZoom(15)
      return
    }
    const lats = pins.map((p) => p.lat)
    const lngs = pins.map((p) => p.lng)
    map.fitBounds(
      {
        north: Math.max(...lats),
        south: Math.min(...lats),
        east: Math.max(...lngs),
        west: Math.min(...lngs),
      },
      40,
    )
    // Refit only when pins are added or removed, not on every edit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, signature])
  return null
}

export function PlacesMap({
  pins,
  center,
  selectedId,
  onSelect,
}: {
  pins: PinOut[]
  center: { lat: number; lng: number }
  selectedId: number | null
  onSelect: (id: number) => void
}) {
  if (!KEY || !MAP_ID) {
    return (
      <div className="flex h-full items-center justify-center bg-gray-100 p-4 text-center text-sm text-gray-500">
        지도를 보려면 .env에 VITE_GOOGLE_MAPS_JS_KEY와 VITE_GOOGLE_MAP_ID를 넣고 다시 빌드하세요.
      </div>
    )
  }
  const shown = located(pins)
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
        {shown.map((p) => {
          const color = isPriority(p.priority) ? PRIORITY_COLORS[p.priority] : '#6b7280'
          const selected = p.id === selectedId
          return (
            <AdvancedMarker
              key={p.id}
              position={{ lat: p.lat, lng: p.lng }}
              title={p.label}
              zIndex={selected ? 10 : undefined}
              onClick={() => onSelect(p.id)}
            >
              <Pin
                background={color}
                borderColor={selected ? '#111827' : '#ffffff'}
                glyphColor="#ffffff"
                scale={selected ? 1.3 : 1}
              />
            </AdvancedMarker>
          )
        })}
        <FitToPins pins={shown} />
      </Map>
    </APIProvider>
  )
}
