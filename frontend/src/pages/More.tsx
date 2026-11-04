import { Link } from 'react-router'
import { HealthBadge } from '../components/HealthBadge'

const ITEMS = [
  { to: '/stays', label: '숙소', hint: '동네 점수, 후보 숙소 비교' },
  { to: '/flights', label: '항공', hint: '후보 비교, 현지 가용 시간' },
  { to: '/prep', label: '준비', hint: '체크리스트, 예약 정보' },
  { to: '/settings', label: '설정', hint: 'API 키, Google 사용량' },
]

export function More() {
  return (
    <section>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">더보기</h1>
        <HealthBadge />
      </div>
      <ul className="divide-y divide-gray-200 rounded-xl border border-gray-200 bg-white">
        {ITEMS.map((item) => (
          <li key={item.to}>
            <Link to={item.to} className="flex min-h-14 flex-col justify-center px-4 py-2">
              <span className="font-medium">{item.label}</span>
              <span className="text-sm text-gray-500">{item.hint}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
