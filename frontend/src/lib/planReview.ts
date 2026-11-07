import type { PlanSuggestionsOut } from '../api/client'

/** The latest AI title per date (a rain plan's title wins for its date). */
export function dayTitles(data: PlanSuggestionsOut | undefined): Map<string, string> {
  const out = new Map<string, string>()
  const reviews = [...(data?.reviews ?? [])].sort((a, b) =>
    a.source === b.source ? 0 : a.source === 'rain' ? 1 : -1,
  )
  for (const r of reviews) for (const t of r.day_titles) out.set(t.date, t.title)
  return out
}
