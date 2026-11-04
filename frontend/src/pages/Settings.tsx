import { useHealth, useUsage } from '../api/hooks'
import { capShare } from '../lib/format'

const KEY_LABELS: Record<string, string> = {
  google_maps_server: 'Google 서버 키',
  google_maps_js: 'Google 지도 JS 키',
  google_map_id: 'Google Map ID',
}

const LEVEL_CLASS = {
  ok: 'text-gray-700',
  warn: 'text-amber-700 font-semibold',
  stop: 'text-red-700 font-semibold',
} as const

export function Settings() {
  const health = useHealth()
  const usage = useUsage()

  return (
    <section className="space-y-6">
      <h1 className="text-xl font-bold">설정</h1>

      <div className="rounded-xl border border-gray-200 bg-white p-4">
        <h2 className="mb-2 font-semibold">API 키</h2>
        {health.data ? (
          <ul className="space-y-1 text-sm">
            {Object.entries(health.data.keys).map(([key, ok]) => (
              <li key={key} className="flex justify-between">
                <span>{KEY_LABELS[key] ?? key}</span>
                <span className={ok ? 'text-green-700' : 'text-gray-400'}>
                  {ok ? '설정됨' : '없음'}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-gray-500">불러오는 중…</p>
        )}
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-4">
        <h2 className="mb-1 font-semibold">이번 달 Google 사용량</h2>
        {usage.data ? (
          <>
            <p className="mb-3 text-xs text-gray-500">
              {usage.data.month} · 무료 한도 {usage.data.caps_as_of} 기준 · 한도의{' '}
              {Math.round(usage.data.warn_ratio * 100)}%에서 경고,{' '}
              {Math.round(usage.data.stop_ratio * 100)}%에서 차단 ·{' '}
              <a
                href={usage.data.caps_source_url}
                className="underline"
                target="_blank"
                rel="noreferrer"
              >
                가격표
              </a>
            </p>
            <ul className="divide-y divide-gray-100 text-sm">
              {usage.data.skus.map((s) => (
                <li key={s.sku} className="flex justify-between gap-3 py-1.5">
                  <span className="truncate font-mono text-xs">{s.sku}</span>
                  <span className={LEVEL_CLASS[s.level]}>
                    {s.count.toLocaleString('ko-KR')} /{' '}
                    {s.cap === null ? '한도 없음' : s.cap.toLocaleString('ko-KR')}
                    {s.cap !== null && ` (${capShare(s.count, s.cap)})`}
                  </span>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="text-sm text-gray-500">
            {usage.isError ? '사용량을 불러오지 못했습니다' : '불러오는 중…'}
          </p>
        )}
      </div>
    </section>
  )
}
