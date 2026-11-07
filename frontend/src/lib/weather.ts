import type { WeatherOut } from '../api/client'

// WMO weather interpretation codes as Open-Meteo documents them (https://open-meteo.com/en/docs).
const GROUPS: [number[], string, string][] = [
  [[0], '☀️', '맑음'],
  [[1, 2], '🌤️', '구름 조금'],
  [[3], '☁️', '흐림'],
  [[45, 48], '🌫️', '안개'],
  [[51, 53, 55, 56, 57], '🌦️', '이슬비'],
  [[61, 63, 65, 66, 67, 80, 81, 82], '🌧️', '비'],
  [[71, 73, 75, 77, 85, 86], '🌨️', '눈'],
  [[95, 96, 99], '⛈️', '뇌우'],
]

/** Emoji and Korean label for a WMO code. */
export function weatherLook(code: number | null | undefined): { icon: string; text: string } {
  const hit = GROUPS.find(([codes]) => code !== null && code !== undefined && codes.includes(code))
  return hit ? { icon: hit[1], text: hit[2] } : { icon: '🌡️', text: '날씨' }
}

/** One-line summary, e.g. "🌧️ 비 · 4°/11° · 강수 80%" or "평년 4°/11° · 비 온 해 40%". */
export function weatherLine(w: WeatherOut): string {
  const temp =
    w.tmin !== null && w.tmax !== null ? `${Math.round(w.tmin)}°/${Math.round(w.tmax)}°` : null
  if (w.kind === 'climate') {
    const parts = [
      temp ? `평년 ${temp}` : '평년',
      w.precip_prob !== null ? `비 온 해 ${w.precip_prob}%` : null,
    ]
    return parts.filter(Boolean).join(' · ')
  }
  const look = weatherLook(w.code)
  const parts = [
    `${look.icon} ${look.text}`,
    temp,
    w.precip_prob !== null ? `강수 ${w.precip_prob}%` : null,
  ]
  return parts.filter(Boolean).join(' · ')
}
