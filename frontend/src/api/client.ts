import type { components } from './schema'

type S = components['schemas']
export type HealthResponse = S['HealthResponse']
export type UsageResponse = S['UsageResponse']
export type SkuUsageOut = S['SkuUsageOut']
export type CityOut = S['CityOut']
export type TripOut = S['TripOut']
export type TripIn = S['TripIn']
export type TripPatch = S['TripPatch']
export type CategoryOut = S['CategoryOut']
export type SuggestionOut = S['AutocompleteOut']
export type ResolveUrlOut = S['ResolveUrlOut']
export type PinOut = S['PinOut']
export type PinCreate = S['PinCreate']
export type PinPatch = S['PinPatch']
export type JobStatus = S['JobStatus']
export type StayOut = S['StayOut']
export type StayIn = S['StayIn']
export type StayPatch = S['StayPatch']
export type ScoreOut = S['ScoreOut']
export type OriginOut = S['OriginOut']
export type FxOut = S['FxOut']
export type AirportOut = S['AirportOut']
export type FlightOut = S['FlightOut']
export type FlightIn = S['FlightIn']
export type LegIn = S['LegIn']
export type LegOut = S['LegOut']
export type EvaluationOut = S['EvaluationOut']
export type AiSuggestionOut = S['AiSuggestionOut']
export type SearchLinksOut = S['SearchLinksOut']
export type LinkOut = S['LinkOut']
export type FaresOut = S['FaresOut']
export type FareOut = S['FareOut']
export type HotelsOut = S['HotelsOut']
export type VacancyOut = S['VacancyOut']
export type HistoryPoint = S['HistoryPoint']
export type FarePrefsIO = S['FarePrefsIO']
export type FarePrefsOut = S['FarePrefsOut']

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

/** Build an ApiError from a failed response, preferring the server's Korean `detail` message. */
async function toError(resp: Response): Promise<ApiError> {
  let message = `${resp.status} ${resp.statusText}`
  try {
    const body = (await resp.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') message = body.detail
  } catch {
    // not JSON
  }
  return new ApiError(resp.status, message)
}

export async function apiGet<T>(path: string, params: Record<string, QueryValue> = {}): Promise<T> {
  const resp = await fetch(`/api${path}${toQuery(params)}`)
  if (!resp.ok) throw await toError(resp)
  return (await resp.json()) as T
}

export async function apiSend<T>(
  method: 'POST' | 'PATCH' | 'PUT' | 'DELETE',
  path: string,
  body?: unknown,
): Promise<T> {
  const resp = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!resp.ok) throw await toError(resp)
  return (resp.status === 204 ? undefined : await resp.json()) as T
}
