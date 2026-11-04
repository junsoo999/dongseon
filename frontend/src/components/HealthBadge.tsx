import { useHealth } from '../api/hooks'

export function HealthBadge() {
  const { data, isPending, isError } = useHealth()

  if (isPending) {
    return <span className="text-sm text-gray-500">서버 확인 중…</span>
  }
  if (isError) {
    return (
      <span className="rounded bg-red-100 px-2 py-1 text-sm text-red-700">백엔드 연결 실패</span>
    )
  }
  return (
    <span className="rounded bg-green-100 px-2 py-1 text-sm text-green-800">
      백엔드 정상 · v{data.version}
    </span>
  )
}
