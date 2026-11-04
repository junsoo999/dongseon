import { useState } from 'react'
import type { SuggestionOut } from '../api/client'
import { useCreatePin, useResolveUrl } from '../api/hooks'
import { newSessionToken } from '../lib/places'
import { BottomSheet } from './BottomSheet'
import { SearchPicker } from './SearchPicker'

type Tab = 'search' | 'link'

interface Picked {
  googlePlaceId: string | null
  label: string
  source: 'search' | 'url'
  sourceRef: string
}

const inputClass = 'min-h-11 w-full rounded-lg border border-gray-300 px-3 text-base'
const primaryButton =
  'min-h-11 w-full rounded-lg bg-teal-700 px-4 font-semibold text-white disabled:opacity-50'

export function AddPlaceSheet({
  tripId,
  open,
  onClose,
}: {
  tripId: number
  open: boolean
  onClose: () => void
}) {
  const [tab, setTab] = useState<Tab>('search')
  const [token, setToken] = useState(newSessionToken)
  const [picked, setPicked] = useState<Picked | null>(null)
  const [url, setUrl] = useState('')
  const [notice, setNotice] = useState<string | null>(null)
  const createPin = useCreatePin(tripId)
  const resolveUrl = useResolveUrl()

  const reset = () => {
    setPicked(null)
    setUrl('')
    setToken(newSessionToken())
    resolveUrl.reset()
    createPin.reset()
  }

  const close = () => {
    reset()
    setNotice(null)
    onClose()
  }

  const onPick = (s: SuggestionOut, query: string) => {
    setNotice(null)
    // The label defaults to what the user typed: Google's place name is not stored (docs/google-terms.md).
    setPicked({
      googlePlaceId: s.google_place_id,
      label: query,
      source: 'search',
      sourceRef: query,
    })
  }

  const onResolve = () => {
    setNotice(null)
    resolveUrl.mutate(
      { trip_id: tripId, url: url.trim() },
      {
        onSuccess: (r) =>
          setPicked({
            googlePlaceId: r.google_place_id,
            label: r.label_hint ?? '',
            source: 'url',
            sourceRef: url.trim(),
          }),
      },
    )
  }

  const onAdd = () => {
    if (!picked) return
    createPin.mutate(
      {
        google_place_id: picked.googlePlaceId,
        label: picked.label.trim(),
        source: picked.source,
        source_ref: picked.sourceRef || null,
        session_token: picked.source === 'search' ? token : null,
      },
      {
        onSuccess: (pin) => {
          reset()
          setNotice(`'${pin.label}'을(를) 추가했습니다`)
        },
      },
    )
  }

  return (
    <BottomSheet open={open} title="장소 추가" onClose={close}>
      <div role="tablist" className="mb-3 grid grid-cols-2 rounded-lg bg-gray-100 p-1 text-sm">
        {(['search', 'link'] as const).map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            onClick={() => {
              reset()
              setTab(t)
            }}
            className={`min-h-10 rounded-md ${tab === t ? 'bg-white font-semibold shadow-sm' : 'text-gray-600'}`}
          >
            {t === 'search' ? '검색' : '지도 링크'}
          </button>
        ))}
      </div>

      {notice && (
        <p className="mb-3 rounded-lg bg-teal-50 px-3 py-2 text-sm text-teal-800">{notice}</p>
      )}

      {picked ? (
        <div className="space-y-3">
          {picked.source === 'url' && (
            <p
              className={`rounded-lg px-3 py-2 text-sm ${picked.googlePlaceId ? 'bg-gray-50 text-gray-700' : 'bg-amber-50 text-amber-800'}`}
            >
              {picked.googlePlaceId
                ? 'Google 장소를 찾았습니다.'
                : `${resolveUrl.data?.reason ?? '장소를 찾지 못했습니다'}. 일단 추가하고 나중에 연결할 수 있습니다.`}
            </p>
          )}
          <label className="block text-sm">
            <span className="mb-1 block text-gray-600">이름 (내가 부를 이름)</span>
            <input
              value={picked.label}
              onChange={(e) => setPicked({ ...picked, label: e.target.value })}
              className={inputClass}
              maxLength={100}
            />
          </label>
          {createPin.error && <p className="text-sm text-red-700">{createPin.error.message}</p>}
          <button
            type="button"
            onClick={onAdd}
            disabled={!picked.label.trim() || createPin.isPending}
            className={primaryButton}
          >
            {createPin.isPending ? '추가 중…' : '이 여행에 추가'}
          </button>
          <button type="button" onClick={reset} className="min-h-11 w-full text-sm text-gray-600">
            다시 고르기
          </button>
        </div>
      ) : tab === 'search' ? (
        <SearchPicker tripId={tripId} sessionToken={token} onPick={onPick} />
      ) : (
        <div className="space-y-3">
          <textarea
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            rows={3}
            placeholder="Google 지도 앱의 공유 → 링크 복사로 받은 주소를 붙여넣으세요"
            className="w-full rounded-lg border border-gray-300 p-3 text-base"
          />
          {resolveUrl.error && <p className="text-sm text-red-700">{resolveUrl.error.message}</p>}
          <button
            type="button"
            onClick={onResolve}
            disabled={url.trim().length < 8 || resolveUrl.isPending}
            className={primaryButton}
          >
            {resolveUrl.isPending ? '찾는 중…' : '장소 찾기'}
          </button>
        </div>
      )}
    </BottomSheet>
  )
}
