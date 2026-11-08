import { savedAtLabel } from '../lib/offline'
import { useOffline } from '../lib/useOffline'

/** Shown when the phone is offline or the home Mac cannot be reached. */
export function OfflineBanner() {
  const { online, tripsDown, bundle } = useOffline()
  if (online && !tripsDown) return null
  return (
    <div
      role="status"
      className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900"
    >
      📴 {online ? '집 Mac에 연결할 수 없습니다' : '오프라인입니다'}
      {bundle
        ? ` · ${savedAtLabel(bundle.generated_at)}에 저장한 일정·준비물을 보여 줍니다 (오늘·준비 탭)`
        : ' · 이 휴대폰에 저장된 일정이 없습니다'}
    </div>
  )
}
