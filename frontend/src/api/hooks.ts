import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { isUnreachable, loadBundle, saveBundle } from '../lib/offline'
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
  type ScoreOut,
  type StayIn,
  type StayOut,
  type StayPatch,
  type FxOut,
  type TodayOut,
  type WeatherListOut,
  type AlertOut,
  type AppliedOut,
  type BookingsOut,
  type LocalNamesOut,
  type ChecklistIn,
  type ChecklistItemOut,
  type ChecklistOut,
  type ChecklistPatch,
  type OfflineOut,
  type AirportOut,
  type FlightIn,
  type FlightOut,
  type AiSuggestionOut,
  type SearchLinksOut,
  type FaresOut,
  type HotelsOut,
  type FarePrefsIO,
  type FarePrefsOut,
  type EditIn,
  type HoursIn,
  type HoursOut,
  type PlanSuggestionsOut,
  type AreaNoteOut,
  type BookingOut,
  type HoursResearchOut,
  type PreviewOut,
  type ReviewIn,
  type ItineraryOut,
  type VersionOut,
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

export function useStays(tripId: number | null) {
  return useQuery({
    queryKey: ['stays', tripId],
    queryFn: () => apiGet<StayOut[]>(`/trips/${tripId}/stays`),
    enabled: tripId !== null,
  })
}

export function useStayScore(tripId: number | null) {
  return useQuery({
    queryKey: ['stayScore', tripId],
    queryFn: () => apiGet<ScoreOut>(`/trips/${tripId}/stays/score`),
    enabled: tripId !== null,
  })
}

export function useFx(base: string) {
  return useQuery({
    queryKey: ['fx', base],
    queryFn: () => apiGet<FxOut | null>('/fx', { base }),
    staleTime: 60 * 60_000,
  })
}

function useInvalidateStays(tripId: number | null) {
  const qc = useQueryClient()
  return () => {
    void qc.invalidateQueries({ queryKey: ['stays', tripId] })
    void qc.invalidateQueries({ queryKey: ['stayScore', tripId] })
    void qc.invalidateQueries({ queryKey: ['usage'] })
  }
}

export function useCreateStay(tripId: number | null) {
  const invalidate = useInvalidateStays(tripId)
  return useMutation({
    mutationFn: (body: Partial<StayIn> & { label: string }) =>
      apiSend<StayOut>('POST', `/trips/${tripId}/stays`, body),
    onSuccess: invalidate,
  })
}

export function useUpdateStay(tripId: number | null) {
  const invalidate = useInvalidateStays(tripId)
  return useMutation({
    mutationFn: ({ id, ...body }: Partial<StayPatch> & { id: number }) =>
      apiSend<StayOut>('PATCH', `/trips/${tripId}/stays/${id}`, body),
    onSuccess: invalidate,
  })
}

export function useDeleteStay(tripId: number | null) {
  const invalidate = useInvalidateStays(tripId)
  return useMutation({
    mutationFn: (id: number) => apiSend<void>('DELETE', `/trips/${tripId}/stays/${id}`),
    onSuccess: invalidate,
  })
}

export function useAirports() {
  return useQuery({
    queryKey: ['airports'],
    queryFn: () => apiGet<AirportOut[]>('/airports'),
    staleTime: Infinity,
  })
}

export function useFlights(tripId: number | null) {
  return useQuery({
    queryKey: ['flights', tripId],
    queryFn: () => apiGet<FlightOut[]>(`/trips/${tripId}/flights`),
    enabled: tripId !== null,
  })
}

function useInvalidateFlights(tripId: number | null) {
  const qc = useQueryClient()
  return () => void qc.invalidateQueries({ queryKey: ['flights', tripId] })
}

export function useSaveFlight(tripId: number | null) {
  const invalidate = useInvalidateFlights(tripId)
  return useMutation({
    mutationFn: ({ id, body }: { id: number | null; body: FlightIn }) =>
      id === null
        ? apiSend<FlightOut>('POST', `/trips/${tripId}/flights`, body)
        : apiSend<FlightOut>('PUT', `/trips/${tripId}/flights/${id}`, body),
    onSuccess: invalidate,
  })
}

export function useDeleteFlight(tripId: number | null) {
  const invalidate = useInvalidateFlights(tripId)
  return useMutation({
    mutationFn: (id: number) => apiSend<void>('DELETE', `/trips/${tripId}/flights/${id}`),
    onSuccess: invalidate,
  })
}

export type JobName =
  | 'places-resolve'
  | 'scout'
  | 'prices'
  | 'review'
  | 'hours-research'
  | 'area-notes'
  | 'weather'
  | 'hours-refresh'
  | 'local-names'

/** A background job's state; polls every 5 s while it runs. */
export function useJob(name: JobName) {
  return useQuery({
    queryKey: ['job', name],
    queryFn: () => apiGet<JobStatus>(`/jobs/${name}`),
    refetchInterval: (q) => (q.state.data?.running ? 5_000 : false),
  })
}

export function useStartJob(name: JobName) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiSend<JobStatus>('POST', `/jobs/${name}`),
    onSuccess: (status) => qc.setQueryData(['job', name], status),
  })
}

export function useSuggestions(tripId: number | null, kind: 'place' | 'stay') {
  return useQuery({
    queryKey: ['suggestions', tripId, kind],
    queryFn: () => apiGet<AiSuggestionOut[]>(`/trips/${tripId}/suggestions`, { kind }),
    enabled: tripId !== null,
  })
}

export function useDecideSuggestion(tripId: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, accept }: { id: number; accept: boolean }) =>
      apiSend<unknown>('POST', `/suggestions/${id}/${accept ? 'accept' : 'reject'}`),
    onSuccess: () => {
      for (const key of ['suggestions', 'pins', 'stays', 'stayScore', 'trips']) {
        void qc.invalidateQueries({ queryKey: [key, tripId] })
      }
      void qc.invalidateQueries({ queryKey: ['trips'] })
    },
  })
}

export function useSearchLinks(tripId: number | null) {
  return useQuery({
    queryKey: ['searchLinks', tripId],
    queryFn: () => apiGet<SearchLinksOut>(`/trips/${tripId}/search-links`),
    enabled: tripId !== null,
    staleTime: 10 * 60_000,
  })
}

export function useFares(tripId: number | null) {
  return useQuery({
    queryKey: ['fares', tripId],
    queryFn: () => apiGet<FaresOut>(`/trips/${tripId}/fares`),
    enabled: tripId !== null,
  })
}

export function useHotels(tripId: number | null) {
  return useQuery({
    queryKey: ['hotels', tripId],
    queryFn: () => apiGet<HotelsOut>(`/trips/${tripId}/hotels`),
    enabled: tripId !== null,
  })
}

export function useAddOffer(tripId: number | null, kind: 'fares' | 'hotels') {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiSend<unknown>('POST', `/trips/${tripId}/${kind}/${id}/add`),
    onSuccess: () => {
      for (const key of ['flights', 'stays', 'stayScore'])
        void qc.invalidateQueries({ queryKey: [key, tripId] })
    },
  })
}

export function useFarePrefs(tripId: number | null) {
  return useQuery({
    queryKey: ['farePrefs', tripId],
    queryFn: () => apiGet<FarePrefsOut>(`/trips/${tripId}/fare-prefs`),
    enabled: tripId !== null,
  })
}

export function useSaveFarePrefs(tripId: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: FarePrefsIO) =>
      apiSend<FarePrefsOut>('PUT', `/trips/${tripId}/fare-prefs`, body),
    onSuccess: (data) => qc.setQueryData(['farePrefs', tripId], data),
  })
}

export function useActiveItinerary(tripId: number | null) {
  return useQuery({
    queryKey: ['itinerary', tripId],
    queryFn: () => apiGet<ItineraryOut | null>(`/trips/${tripId}/itineraries/active`),
    enabled: tripId !== null,
  })
}

export function useItineraryVersions(tripId: number | null) {
  return useQuery({
    queryKey: ['itineraryVersions', tripId],
    queryFn: () => apiGet<VersionOut[]>(`/trips/${tripId}/itineraries`),
    enabled: tripId !== null,
  })
}

function useNewVersion<V>(tripId: number | null, send: (v: V) => Promise<ItineraryOut>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: send,
    onSuccess: (data) => {
      qc.setQueryData(['itinerary', tripId], data)
      void qc.invalidateQueries({ queryKey: ['itineraryVersions', tripId] })
      void qc.invalidateQueries({ queryKey: ['usage'] })
      void qc.invalidateQueries({ queryKey: ['alerts', tripId] })
      void qc.invalidateQueries({ queryKey: ['today', tripId] })
      void qc.invalidateQueries({ queryKey: ['offline', tripId] })
    },
  })
}

export function useSolveItinerary(tripId: number | null) {
  return useNewVersion<void>(tripId, () =>
    apiSend<ItineraryOut>('POST', `/trips/${tripId}/itineraries/solve`),
  )
}

/** Save an edited layout as a new version (``resolve`` re-solves the unlocked pins). */
export function useEditItinerary(tripId: number | null) {
  return useNewVersion<{ id: number; body: EditIn }>(tripId, ({ id, body }) =>
    apiSend<ItineraryOut>('POST', `/itineraries/${id}/edit`, body),
  )
}

/** Re-solve keeping locked visits and removed pins. */
export function useResolveItinerary(tripId: number | null) {
  return useNewVersion<number>(tripId, (id) =>
    apiSend<ItineraryOut>('POST', `/itineraries/${id}/resolve`),
  )
}

/** Make a new version from an older version's layout. */
export function useRestoreItinerary(tripId: number | null) {
  return useNewVersion<number>(tripId, (id) =>
    apiSend<ItineraryOut>('POST', `/itineraries/${id}/restore`),
  )
}

export function useItinerary(id: number | null) {
  return useQuery({
    queryKey: ['itineraryVersion', id],
    queryFn: () => apiGet<ItineraryOut>(`/itineraries/${id}`),
    enabled: id !== null,
  })
}

/** Set (``body``) or clear (``body: null``) the user's hours for a pin on a date. */
export function useSetHours(tripId: number | null) {
  return useMutation({
    mutationFn: ({ pinId, day, body }: { pinId: number; day: string; body: HoursIn | null }) =>
      body
        ? apiSend<HoursOut>('PUT', `/trips/${tripId}/pins/${pinId}/hours/${day}`, body)
        : apiSend<null>('DELETE', `/trips/${tripId}/pins/${pinId}/hours/${day}`),
  })
}

/** Pending AI day titles, notes and edits for the trip's plan. */
export function usePlanSuggestions(tripId: number | null) {
  return useQuery({
    queryKey: ['planSuggestions', tripId],
    queryFn: () => apiGet<PlanSuggestionsOut>(`/trips/${tripId}/plan-suggestions`),
    enabled: tripId !== null,
  })
}

/** The review job's state; refreshes the plan suggestions when it finishes. */
export function useReviewJob(tripId: number | null) {
  const job = useJob('review')
  const qc = useQueryClient()
  const running = job.data?.running ?? false
  const was = useRef(false)
  useEffect(() => {
    if (was.current && !running)
      void qc.invalidateQueries({ queryKey: ['planSuggestions', tripId] })
    was.current = running
  }, [running, qc, tripId])
  return job
}

/** Start the AI review (or a rain plan for ``rain_date``) of the active version. */
export function useStartReview() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: ReviewIn }) =>
      apiSend<JobStatus>('POST', `/itineraries/${id}/review`, body),
    onSuccess: (status) => qc.setQueryData(['job', 'review'], status),
  })
}

/** An AI edit applied to the current version, not saved. */
export function usePlanPreview(id: number | null) {
  return useQuery({
    queryKey: ['planPreview', id],
    queryFn: () => apiGet<PreviewOut>(`/plan-suggestions/${id}/preview`),
    enabled: id !== null,
    staleTime: 0,
  })
}

/** Accept an AI edit: a new version (origin "ai"). */
export function useAcceptPlanSuggestion(tripId: number | null) {
  const qc = useQueryClient()
  const save = useNewVersion<number>(tripId, (id) =>
    apiSend<ItineraryOut>('POST', `/plan-suggestions/${id}/accept`),
  )
  return {
    ...save,
    mutate: (id: number, opts?: { onSuccess?: () => void }) =>
      save.mutate(id, {
        onSuccess: () => {
          void qc.invalidateQueries({ queryKey: ['planSuggestions', tripId] })
          void qc.invalidateQueries({ queryKey: ['planPreview'] })
          void qc.invalidateQueries({ queryKey: ['pins', tripId] })
          opts?.onSuccess?.()
        },
      }),
  }
}

/** Reject an AI edit, or dismiss a review's titles and notes. */
export function useRejectPlanSuggestion(tripId: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiSend<null>('POST', `/plan-suggestions/${id}/reject`),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['planSuggestions', tripId] }),
  })
}

/** Holiday dates of the trip and the AI-researched hours of its must/want pins. */
export function useHoursResearch(tripId: number | null) {
  return useQuery({
    queryKey: ['hoursResearch', tripId],
    queryFn: () => apiGet<HoursResearchOut>(`/trips/${tripId}/hours-research`),
    enabled: tripId !== null,
  })
}

/** The latest AI note per stay area. */
export function useAreaNotes(tripId: number | null) {
  return useQuery({
    queryKey: ['areaNotes', tripId],
    queryFn: () => apiGet<AreaNoteOut[]>(`/trips/${tripId}/area-notes`),
    enabled: tripId !== null,
  })
}

/** Read a pasted booking email into a draft (nothing is saved). */
export function useParseBooking(tripId: number | null) {
  return useMutation({
    mutationFn: (text: string) =>
      apiSend<BookingOut>('POST', `/trips/${tripId}/parse-booking`, { text }),
  })
}

/** The today tab: today's day during the trip (the first day before it), weather and the JPY rate. */
export function useToday(tripId: number | null) {
  return useQuery({
    queryKey: ['today', tripId],
    queryFn: () => apiGet<TodayOut>(`/trips/${tripId}/today`),
    enabled: tripId !== null,
    refetchInterval: 10 * 60_000,
  })
}

/** Stored weather per trip date (forecast, else past-years climate). */
export function useTripWeather(tripId: number | null) {
  return useQuery({
    queryKey: ['weather', tripId],
    queryFn: () => apiGet<WeatherListOut>(`/trips/${tripId}/weather`),
    enabled: tripId !== null,
  })
}

/** Open alerts about the active version (e.g. warnings changed by the D-7 hours re-check). */
export function useAlerts(tripId: number | null) {
  return useQuery({
    queryKey: ['alerts', tripId],
    queryFn: () => apiGet<AlertOut[]>(`/trips/${tripId}/alerts`),
    enabled: tripId !== null,
  })
}

export function useDismissAlert(tripId: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiSend<null>('POST', `/alerts/${id}/dismiss`),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['alerts', tripId] }),
  })
}

export function useChecklist(tripId: number | null) {
  return useQuery({
    queryKey: ['checklist', tripId],
    queryFn: () => apiGet<ChecklistOut>(`/trips/${tripId}/checklist`),
    enabled: tripId !== null,
  })
}

function useChecklistMutation<V, R>(tripId: number | null, send: (v: V) => Promise<R>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: send,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['checklist', tripId] })
      void qc.invalidateQueries({ queryKey: ['offline', tripId] })
    },
  })
}

/** Copy the template lines the trip does not have yet. */
export function useSeedChecklist(tripId: number | null) {
  return useChecklistMutation(tripId, () =>
    apiSend<ChecklistOut>('POST', `/trips/${tripId}/checklist/seed`),
  )
}

export function useAddChecklistItem(tripId: number | null) {
  return useChecklistMutation(tripId, (body: ChecklistIn) =>
    apiSend<ChecklistItemOut>('POST', `/trips/${tripId}/checklist`, body),
  )
}

export function usePatchChecklistItem(tripId: number | null) {
  return useChecklistMutation(tripId, ({ id, ...body }: ChecklistPatch & { id: number }) =>
    apiSend<ChecklistItemOut>('PATCH', `/checklist/${id}`, body),
  )
}

export function useDeleteChecklistItem(tripId: number | null) {
  return useChecklistMutation(tripId, (id: number) => apiSend<null>('DELETE', `/checklist/${id}`))
}

/** Booked flights, booked stays and reserved time slots. */
export function useBookings(tripId: number | null) {
  return useQuery({
    queryKey: ['bookings', tripId],
    queryFn: () => apiGet<BookingsOut>(`/trips/${tripId}/bookings`),
    enabled: tripId !== null,
  })
}

export type OfflineState = { bundle: OfflineOut | null; live: boolean }

/**
 * The phone's offline copy: fetched and stored whenever the server answers, read back from IndexedDB when
 * it cannot be reached. With no trip id (the trip list did not load), the latest stored copy is used.
 */
export function useOfflineBundle(tripId: number | null, fallbackLatest = false) {
  return useQuery({
    queryKey: ['offline', tripId],
    queryFn: async (): Promise<OfflineState> => {
      if (tripId !== null) {
        try {
          const bundle = await apiGet<OfflineOut>(`/trips/${tripId}/offline`)
          await saveBundle(bundle)
          return { bundle, live: true }
        } catch (e) {
          if (!isUnreachable(e)) throw e
        }
      }
      return { bundle: await loadBundle(tripId), live: false }
    },
    enabled: tripId !== null || fallbackLatest,
    refetchInterval: 10 * 60_000,
    retry: false,
  })
}

/** Local-name coverage and pending AI suggestions. */
export function useLocalNames(tripId: number | null) {
  return useQuery({
    queryKey: ['localNames', tripId],
    queryFn: () => apiGet<LocalNamesOut>(`/trips/${tripId}/local-names`),
    enabled: tripId !== null,
  })
}

function useLocalNameMutation<V, R>(tripId: number | null, send: (v: V) => Promise<R>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: send,
    onSuccess: () => {
      for (const key of ['localNames', 'pins', 'offline'])
        void qc.invalidateQueries({ queryKey: [key, tripId] })
    },
  })
}

/** Apply one suggested local name. */
export function useAcceptLocalName(tripId: number | null) {
  return useLocalNameMutation(tripId, (id: number) =>
    apiSend<null>('POST', `/local-names/${id}/accept`),
  )
}

/** Reject one suggested local name. */
export function useRejectLocalName(tripId: number | null) {
  return useLocalNameMutation(tripId, (id: number) =>
    apiSend<null>('POST', `/local-names/${id}/reject`),
  )
}

/** Apply every suggestion the search confirmed. */
export function useAcceptVerifiedLocalNames(tripId: number | null) {
  return useLocalNameMutation(tripId, () =>
    apiSend<AppliedOut>('POST', `/trips/${tripId}/local-names/accept-verified`),
  )
}
