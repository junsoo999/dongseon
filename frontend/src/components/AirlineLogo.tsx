import { useState } from 'react'
import { airlineLogoUrl } from '../lib/airlines'

/** Airline logo in a white tile; shows the IATA code when the image is unavailable. */
export function AirlineLogo({
  code,
  name,
  size = 36,
}: {
  code: string | null
  name?: string | null
  size?: number
}) {
  const [failed, setFailed] = useState(false)
  const box = { width: size, height: size }
  if (!code || failed) {
    return (
      <span
        style={box}
        className="flex shrink-0 items-center justify-center rounded-xl bg-slate-100 text-xs font-bold text-slate-600"
      >
        {code ?? '✈️'}
      </span>
    )
  }
  return (
    <span
      style={box}
      className="flex shrink-0 items-center justify-center rounded-xl bg-white p-1 ring-1 ring-gray-200"
    >
      <img
        src={airlineLogoUrl(code, size * 2)}
        alt={name ?? code}
        loading="lazy"
        onError={() => setFailed(true)}
        className="max-h-full max-w-full object-contain"
      />
    </span>
  )
}
