/**
 * Color roles: teal = the user's own actions, violet = AI analysis (Claude), sky = data fetched automatically
 * from outside services (fares, vacancies). White outline is for secondary actions only.
 */
const base =
  'inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl px-4 text-sm font-semibold disabled:opacity-50'

export const BTN = {
  primary: `${base} bg-teal-700 text-white hover:bg-teal-800`,
  ai: `${base} bg-violet-600 text-white hover:bg-violet-700`,
  live: `${base} bg-sky-600 text-white hover:bg-sky-700`,
  secondary: `${base} border border-gray-300 bg-white font-medium text-gray-800 hover:bg-gray-50`,
} as const

export const PANEL = {
  ai: 'rounded-2xl border border-violet-200 bg-violet-50/60',
  live: 'rounded-2xl border border-sky-200 bg-sky-50/60',
} as const

export const BADGE = {
  ai: 'rounded-md bg-violet-100 px-1.5 py-0.5 text-xs font-medium text-violet-800',
  live: 'rounded-md bg-sky-100 px-1.5 py-0.5 text-xs font-medium text-sky-800',
} as const

export type Tone = 'ai' | 'live'
