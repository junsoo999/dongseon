import type { components } from './schema'

type S = components['schemas']
export type HealthResponse = S['HealthResponse']
export type UsageResponse = S['UsageResponse']
export type SkuUsageOut = S['SkuUsageOut']

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export type QueryValue = string | number | boolean | null | undefined | Array<string | number>

/** Build `?a=1&b=2&b=3` from an object, skipping empty values. */
export function toQuery(params: Record<string, QueryValue>): string {
  const q = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '') continue
    if (Array.isArray(value)) value.forEach((v) => q.append(key, String(v)))
    else q.set(key, String(value))
  }
  const s = q.toString()
  return s ? `?${s}` : ''
}

export async function apiGet<T>(path: string, params: Record<string, QueryValue> = {}): Promise<T> {
  const resp = await fetch(`/api${path}${toQuery(params)}`)
  if (!resp.ok) {
    throw new ApiError(resp.status, `${resp.status} ${resp.statusText}`)
  }
  return (await resp.json()) as T
}

export async function apiSend<T>(
  method: 'POST' | 'PATCH' | 'DELETE',
  path: string,
  body?: unknown,
): Promise<T> {
  const resp = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!resp.ok) {
    throw new ApiError(resp.status, `${resp.status} ${resp.statusText}`)
  }
  return (resp.status === 204 ? undefined : await resp.json()) as T
}
