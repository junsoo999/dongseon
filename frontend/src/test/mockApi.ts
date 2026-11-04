import { vi } from 'vitest'

const IDLE_JOB = {
  name: 'scout',
  running: false,
  last_status: null,
  last_ran_at: null,
  last_rows: null,
  last_error: null,
}

/**
 * Stub `fetch` with a route table: the first entry whose path fragment occurs in the URL wins.
 * Jobs, suggestions and search links answer with empty defaults unless overridden.
 */
export function mockApi(routes: Array<[string, unknown]>) {
  const table: Array<[string, unknown]> = [
    ...routes,
    ['/api/jobs/', IDLE_JOB],
    ['/suggestions', []],
    ['/search-links', { flights: [], stays: [] }],
  ]
  const fn = vi.fn((url: string) => {
    const hit = table.find(([fragment]) => url.includes(fragment))
    return Promise.resolve(new Response(JSON.stringify(hit ? hit[1] : [])))
  })
  vi.stubGlobal('fetch', fn)
  return fn
}
