import { Link } from 'react-router'
import { useAlerts, useDismissAlert } from '../api/hooks'
import { BTN } from '../lib/theme'

function checkedAt(iso: string): string {
  const d = new Date(iso)
  const hm = d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
  return `${d.getMonth() + 1}/${d.getDate()} ${hm}`
}

/** Warnings that changed when opening hours were re-checked (from D-7), for the active version. */
export function HoursAlert({
  tripId,
  onResolve,
  busy = false,
}: {
  tripId: number
  onResolve?: () => void
  busy?: boolean
}) {
  const alerts = useAlerts(tripId)
  const dismiss = useDismissAlert(tripId)
  const a = alerts.data?.[0]
  if (!a) return null
  return (
    <section className="space-y-2 rounded-2xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
      <p className="font-semibold">영업시간을 다시 확인했더니 경고가 달라졌습니다</p>
      {a.added.length > 0 && (
        <ul className="space-y-0.5">
          {a.added.map((x) => (
            <li key={x}>⚠️ {x}</li>
          ))}
        </ul>
      )}
      {a.resolved.length > 0 && (
        <ul className="space-y-0.5 text-amber-900/80">
          {a.resolved.map((x) => (
            <li key={x}>✓ 풀림: {x}</li>
          ))}
        </ul>
      )}
      <p className="text-xs text-amber-900/80">
        {checkedAt(a.created_at)} 확인 · Google 특별 영업시간(7일 이내)과 직접 입력 기준
      </p>
      <div className="flex gap-2">
        {onResolve ? (
          <button
            type="button"
            disabled={busy}
            onClick={onResolve}
            className={`${BTN.primary} flex-1`}
          >
            다시 맞추기
          </button>
        ) : (
          <Link to="/itinerary" className={`${BTN.primary} flex-1`}>
            일정에서 보기
          </Link>
        )}
        <button
          type="button"
          disabled={dismiss.isPending}
          onClick={() => dismiss.mutate(a.id)}
          className={BTN.secondary}
        >
          닫기
        </button>
      </div>
    </section>
  )
}
