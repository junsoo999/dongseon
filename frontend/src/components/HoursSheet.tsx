import { useState } from 'react'
import type { ItemOut } from '../api/client'
import { useSetHours } from '../api/hooks'
import { BTN } from '../lib/theme'
import { BottomSheet } from './BottomSheet'

/** Enter a place's hours for one date (wins over Google and AI research). */
export function HoursSheet({
  tripId,
  item,
  date,
  onClose,
  onSaved,
}: {
  tripId: number
  item: ItemOut
  date: string
  onClose: () => void
  onSaved: () => void
}) {
  const [status, setStatus] = useState<'open' | 'closed'>('open')
  const [open, setOpen] = useState('10:00')
  const [close, setClose] = useState('18:00')
  const save = useSetHours(tripId)
  const pinId = item.pin_id ?? 0
  const done = { onSuccess: onSaved }
  const label = `${Number(date.slice(5, 7))}/${Number(date.slice(8, 10))}`

  return (
    <BottomSheet open title={`${item.label} · ${label} 영업시간`} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-gray-600">
          지금: {item.hours ?? '정보 없음'}. 직접 입력하면 Google·AI 조사보다 먼저 씁니다. 저장하면
          순서는 그대로 두고 시각을 다시 계산합니다.
        </p>
        <div className="flex gap-2" role="radiogroup" aria-label="영업 여부">
          {(
            [
              ['open', '영업'],
              ['closed', '휴무'],
            ] as const
          ).map(([value, text]) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={status === value}
              onClick={() => setStatus(value)}
              className={`min-h-11 flex-1 rounded-xl text-sm font-semibold ${status === value ? 'bg-teal-700 text-white' : 'bg-teal-50 text-teal-800 ring-1 ring-teal-200'}`}
            >
              {text}
            </button>
          ))}
        </div>
        {status === 'open' && (
          <div className="flex items-center gap-2 text-sm">
            <label className="flex flex-1 flex-col gap-1">
              여는 시각
              <input
                type="time"
                value={open}
                onChange={(e) => setOpen(e.target.value)}
                className="min-h-11 rounded-xl border border-gray-300 px-3"
              />
            </label>
            <span className="pt-6">~</span>
            <label className="flex flex-1 flex-col gap-1">
              닫는 시각
              <input
                type="time"
                value={close}
                onChange={(e) => setClose(e.target.value)}
                className="min-h-11 rounded-xl border border-gray-300 px-3"
              />
            </label>
          </div>
        )}
        {save.error && <p className="text-sm text-red-700">{save.error.message}</p>}
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={save.isPending}
            onClick={() =>
              save.mutate(
                {
                  pinId,
                  day: date,
                  body: status === 'open' ? { status, open, close } : { status },
                },
                done,
              )
            }
            className={`${BTN.primary} flex-1`}
          >
            저장
          </button>
          {item.hours_source === 'user' && (
            <button
              type="button"
              disabled={save.isPending}
              onClick={() => save.mutate({ pinId, day: date, body: null }, done)}
              className={BTN.soft}
            >
              직접 입력 지우기
            </button>
          )}
        </div>
      </div>
    </BottomSheet>
  )
}
