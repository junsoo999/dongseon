import { vi } from 'vitest'

const IDLE_JOB = {
  name: 'job',
  running: false,
  last_status: null,
  last_ran_at: null,
  last_rows: null,
  last_error: null,
}

const DEFAULTS: Array<[string, unknown]> = [
  ['/api/jobs/', IDLE_JOB],
  ['/plan-suggestions', { reviews: [], edits: [] }],
  ['/hours-research', { dates: [], holiday_note: null, places: [] }],
  ['/area-notes', []],
  ['/alerts', []],
  ['/checklist', { items: [], template_as_of: '2026-11-08' }],
  ['/bookings', { flights: [], stays: [], reservations: [] }],
  ['/local-names', { total: 0, filled: 0, suggestions: [] }],
  [
    '/offline',
    {
      trip: {
        id: 1,
        title: '도쿄',
        timezone: 'Asia/Tokyo',
        start_date: '2030-12-28',
        end_date: '2030-12-29',
      },
      generated_at: '2030-12-27T00:00:00Z',
      itinerary_id: null,
      version: null,
      days: [],
      checklist: [],
      bookings: { flights: [], stays: [], reservations: [] },
    },
  ],
  [
    '/weather',
    {
      days: [],
      rain_probability_pct: 60,
      attribution: 'Weather data by Open-Meteo.com',
      attribution_url: 'https://open-meteo.com/',
    },
  ],
  ['/suggestions', []],
  ['/search-links', { flights: [], stays: [] }],
  [
    '/fare-prefs',
    {
      adults: 2,
      children: 0,
      origins: ['ICN'],
      destinations: ['HND', 'NRT'],
      max_stops: 0,
      checked_bags: null,
      out_dep_from: null,
      out_dep_to: null,
      back_dep_from: null,
      back_dep_to: null,
      max_price_krw: null,
      airlines_exclude: [],
      airport_choices: ['ICN', 'HND', 'NRT'],
      saved: false,
    },
  ],
  ['/fares', { fetched_at: null, reference_label: null, reference_kind: 'none', items: [] }],
  [
    '/hotels',
    {
      fetched_at: null,
      check_in: null,
      check_out: null,
      credit_text: 'Supported by Rakuten Developers',
      credit_url: 'https://developers.rakuten.com/',
      areas: [],
    },
  ],
]

/**
 * Stub `fetch` with a route table: the first entry whose path fragment occurs in the URL wins.
 * Built-in defaults (jobs, suggestions, links, fares, hotels) are checked first unless a route overrides them.
 */
export function mockApi(routes: Array<[string, unknown]>) {
  const overridden = new Set(routes.map(([f]) => f))
  const table = [...DEFAULTS.filter(([f]) => !overridden.has(f)), ...routes]
  const fn = vi.fn((url: string, _init?: RequestInit) => {
    const hit = table.find(([fragment]) => url.includes(fragment))
    return Promise.resolve(new Response(JSON.stringify(hit ? hit[1] : [])))
  })
  vi.stubGlobal('fetch', fn)
  return fn
}
