import { useState } from 'react'
import type { PinOut, PinPatch } from '../api/client'
import { useCategories, useDeletePin, useUpdatePin } from '../api/hooks'
import { formatMinutes } from '../lib/format'
import {
  categoryLabel,
  isPriority,
  mapsPlaceUrl,
  newSessionToken,
  PRIORITIES,
  PRIORITY_LABELS,
  type Priority,
} from '../lib/places'
import { BottomSheet } from './BottomSheet'
import { SearchPicker } from './SearchPicker'

const DWELL_STEP = 15

interface Draft {
  label: string
  localName: string
  category: string
  priority: Priority
  dwell: number
  meal: '' | 'lunch' | 'dinner'
  note: string
}

function toDraft(pin: PinOut): Draft {
  return {
    label: pin.label,
    localName: pin.local_name ?? '',
    category: pin.category,
    priority: isPriority(pin.priority) ? pin.priority : 'want',
    dwell: pin.dwell_min,
    meal: pin.meal === 'lunch' || pin.meal === 'dinner' ? pin.meal : '',
    note: pin.note ?? '',
  }
}

const inputClass = 'min-h-11 w-full rounded-lg border border-gray-300 px-3 text-base'

export function PinEditSheet({
  tripId,
  pin,
  onClose,
}: {
  tripId: number
  pin: PinOut | null
  onClose: () => void
}) {
  return (
    <BottomSheet open={pin !== null} title="장소 편집" onClose={onClose}>
      {pin && <PinEditForm key={pin.id} tripId={tripId} pin={pin} onClose={onClose} />}
    </BottomSheet>
  )
}

function PinEditForm({
  tripId,
  pin,
  onClose,
}: {
  tripId: number
  pin: PinOut
  onClose: () => void
}) {
  const [draft, setDraft] = useState<Draft>(() => toDraft(pin))
  const [matching, setMatching] = useState(false)
  const [token] = useState(newSessionToken)
  const categories = useCategories()
  const update = useUpdatePin(tripId)
  const remove = useDeletePin(tripId)
  const mapsUrl = mapsPlaceUrl(pin)

  const save = () => {
    const body: Partial<PinPatch> & { id: number } = {
      id: pin.id,
      label: draft.label.trim(),
      local_name: draft.localName,
      category: draft.category,
      priority: draft.priority,
      dwell_min: draft.dwell,
      note: draft.note,
      ...(draft.meal ? { meal: draft.meal } : { clear_meal: true }),
    }
    update.mutate(body, { onSuccess: onClose })
  }

  if (matching) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-gray-600">'{pin.label}'에 연결할 Google 장소를 고르세요.</p>
        <SearchPicker
          tripId={tripId}
          sessionToken={token}
          onPick={(s) =>
            update.mutate(
              { id: pin.id, google_place_id: s.google_place_id },
              { onSuccess: onClose },
            )
          }
        />
        {update.error && <p className="text-sm text-red-700">{update.error.message}</p>}
        <button
          type="button"
          onClick={() => setMatching(false)}
          className="min-h-11 w-full text-sm text-gray-600"
        >
          취소
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {pin.resolve_status !== 'ok' && (
        <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
          아직 Google 장소와 연결되지 않아 지도에 표시되지 않습니다.
          <button
            type="button"
            onClick={() => setMatching(true)}
            className="mt-2 block min-h-11 w-full rounded-lg border border-amber-300 bg-white font-medium"
          >
            Google 장소 연결
          </button>
        </div>
      )}

      <label className="block text-sm">
        <span className="mb-1 block text-gray-600">이름</span>
        <input
          value={draft.label}
          onChange={(e) => setDraft({ ...draft, label: e.target.value })}
          maxLength={100}
          className={inputClass}
        />
      </label>
      <label className="block text-sm">
        <span className="mb-1 block text-gray-600">현지 이름 (선택)</span>
        <input
          value={draft.localName}
          onChange={(e) => setDraft({ ...draft, localName: e.target.value })}
          maxLength={100}
          placeholder="예: 築地場外市場"
          className={inputClass}
        />
        <span className="mt-1 block text-xs text-gray-500">
          내 지도 CSV에서 이 이름으로 위치를 찾습니다.
        </span>
      </label>

      <fieldset>
        <legend className="mb-1 text-sm text-gray-600">우선순위</legend>
        <div className="grid grid-cols-3 gap-2">
          {PRIORITIES.map((p) => (
            <button
              key={p}
              type="button"
              aria-pressed={draft.priority === p}
              onClick={() => setDraft({ ...draft, priority: p })}
              className={`min-h-11 rounded-lg border text-sm ${draft.priority === p ? 'border-teal-700 bg-teal-50 font-semibold text-teal-800' : 'border-gray-300'}`}
            >
              {PRIORITY_LABELS[p]}
            </button>
          ))}
        </div>
      </fieldset>

      <div className="grid grid-cols-2 gap-3">
        <label className="block text-sm">
          <span className="mb-1 block text-gray-600">카테고리</span>
          <select
            value={draft.category}
            onChange={(e) => setDraft({ ...draft, category: e.target.value })}
            className={inputClass}
          >
            {(categories.data ?? [{ key: draft.category, dwell_min: 0 }]).map((c) => (
              <option key={c.key} value={c.key}>
                {categoryLabel(c.key)}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-gray-600">식사</span>
          <select
            value={draft.meal}
            onChange={(e) => setDraft({ ...draft, meal: e.target.value as Draft['meal'] })}
            className={inputClass}
          >
            <option value="">아님</option>
            <option value="lunch">점심</option>
            <option value="dinner">저녁</option>
          </select>
        </label>
      </div>

      <div className="text-sm">
        <span className="mb-1 block text-gray-600">머무는 시간</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-label="15분 줄이기"
            onClick={() => setDraft({ ...draft, dwell: Math.max(5, draft.dwell - DWELL_STEP) })}
            className="min-h-11 min-w-11 rounded-lg border border-gray-300 text-lg"
          >
            −
          </button>
          <span className="min-w-24 text-center text-base font-medium">
            {formatMinutes(draft.dwell)}
          </span>
          <button
            type="button"
            aria-label="15분 늘리기"
            onClick={() => setDraft({ ...draft, dwell: Math.min(720, draft.dwell + DWELL_STEP) })}
            className="min-h-11 min-w-11 rounded-lg border border-gray-300 text-lg"
          >
            +
          </button>
        </div>
      </div>

      <label className="block text-sm">
        <span className="mb-1 block text-gray-600">메모</span>
        <textarea
          value={draft.note}
          onChange={(e) => setDraft({ ...draft, note: e.target.value })}
          rows={2}
          maxLength={2000}
          className="w-full rounded-lg border border-gray-300 p-3 text-base"
        />
      </label>
      {pin.user_note && <p className="text-xs text-gray-500">가져온 메모: {pin.user_note}</p>}

      {update.error && <p className="text-sm text-red-700">{update.error.message}</p>}
      <button
        type="button"
        onClick={save}
        disabled={!draft.label.trim() || update.isPending}
        className="min-h-11 w-full rounded-lg bg-teal-700 font-semibold text-white disabled:opacity-50"
      >
        {update.isPending ? '저장 중…' : '저장'}
      </button>

      <div className="flex gap-2">
        {mapsUrl && (
          <a
            href={mapsUrl}
            target="_blank"
            rel="noreferrer"
            className="flex min-h-11 flex-1 items-center justify-center rounded-lg border border-gray-300 text-sm"
          >
            Google 지도에서 보기
          </a>
        )}
        <button
          type="button"
          onClick={() => {
            if (window.confirm(`'${pin.label}'을(를) 이 여행에서 뺄까요?`)) {
              remove.mutate(pin.id, { onSuccess: onClose })
            }
          }}
          className="min-h-11 flex-1 rounded-lg border border-red-200 text-sm text-red-700"
        >
          여행에서 빼기
        </button>
      </div>
    </div>
  )
}
