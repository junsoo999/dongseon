import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  apiGet,
  apiSend,
  type CategoryOut,
  type CityOut,
  type HealthResponse,
  type JobStatus,
  type PinCreate,
  type PinOut,
  type PinPatch,
  type ResolveUrlOut,
  type SuggestionOut,
  type TripIn,
  type TripOut,
  type UsageResponse,
} from './client'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<HealthResponse>('/health'),
    refetchInterval: 30_000,
  })
}

export function useUsage() {
  return useQuery({
    queryKey: ['usage'],
    queryFn: () => apiGet<UsageResponse>('/usage'),
  })
}

export function useCities() {
  return useQuery({
    queryKey: ['cities'],
    queryFn: () => apiGet<CityOut[]>('/cities'),
    staleTime: Infinity,
  })
}

export function useCategories() {
  return useQuery({
    queryKey: ['categories'],
    queryFn: () => apiGet<CategoryOut[]>('/categories'),
    staleTime: Infinity,
  })
}

export function useTrips() {
  return useQuery({ queryKey: ['trips'], queryFn: () => apiGet<TripOut[]>('/trips') })
}

export function useCreateTrip() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: TripIn) => apiSend<TripOut>('POST', '/trips', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['trips'] }),
  })
}

export function usePins(tripId: number | null) {
  return useQuery({
    queryKey: ['pins', tripId],
    queryFn: () => apiGet<PinOut[]>(`/trips/${tripId}/pins`),
    enabled: tripId !== null,
  })
}

function useInvalidatePins(tripId: number | null) {
  const qc = useQueryClient()
  return () => {
    void qc.invalidateQueries({ queryKey: ['pins', tripId] })
    void qc.invalidateQueries({ queryKey: ['trips'] })
    void qc.invalidateQueries({ queryKey: ['usage'] })
  }
}

export function useCreatePin(tripId: number | null) {
  const invalidate = useInvalidatePins(tripId)
  return useMutation({
    mutationFn: (body: PinCreate) => apiSend<PinOut>('POST', `/trips/${tripId}/pins`, body),
    onSuccess: invalidate,
  })
}

export function useUpdatePin(tripId: number | null) {
  const invalidate = useInvalidatePins(tripId)
  return useMutation({
    mutationFn: ({ id, ...body }: Partial<PinPatch> & { id: number }) =>
      apiSend<PinOut>('PATCH', `/trips/${tripId}/pins/${id}`, body),
    onSuccess: invalidate,
  })
}

export function useDeletePin(tripId: number | null) {
  const invalidate = useInvalidatePins(tripId)
  return useMutation({
    mutationFn: (id: number) => apiSend<void>('DELETE', `/trips/${tripId}/pins/${id}`),
    onSuccess: invalidate,
  })
}

/** Place suggestions; `query` shorter than 2 characters disables the request. */
export function useAutocomplete(tripId: number | null, query: string, sessionToken: string) {
  return useQuery({
    queryKey: ['autocomplete', tripId, query, sessionToken],
    queryFn: () =>
      apiGet<SuggestionOut[]>('/places/autocomplete', {
        trip_id: tripId,
        q: query,
        session_token: sessionToken,
      }),
    enabled: tripId !== null && query.trim().length >= 2,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
    retry: false,
  })
}

export function useResolveUrl() {
  return useMutation({
    mutationFn: (body: { trip_id: number; url: string }) =>
      apiSend<ResolveUrlOut>('POST', '/places/resolve-url', body),
  })
}

export function useStartJob(name: 'places-resolve') {
  return useMutation({ mutationFn: () => apiSend<JobStatus>('POST', `/jobs/${name}`) })
}
