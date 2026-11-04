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
  ['/suggestions', []],
  ['/search-links', { flights: [], stays: [] }],
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
  const fn = vi.fn((url: string) => {
    const hit = table.find(([fragment]) => url.includes(fragment))
    return Promise.resolve(new Response(JSON.stringify(hit ? hit[1] : [])))
  })
  vi.stubGlobal('fetch', fn)
  return fn
}
