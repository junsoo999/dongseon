import { useState } from 'react'
import type { BookingOut } from '../api/client'
import { useParseBooking } from '../api/hooks'
import { BADGE, BTN, PANEL } from '../lib/theme'
import { BottomSheet } from './BottomSheet'
import { LoadingBlock } from './Loading'

const MASKED_ORDER = ['카드번호', '여권번호', '생년월일', '이메일', '전화번호']

/** Paste a booking email, let AI read it (after masking), then continue in the flight or stay form. */
export function BookingPasteSheet({
  tripId,
  onResult,
  onClose,
}: {
  tripId: number
  onResult: (result: BookingOut) => void
  onClose: () => void
}) {
  const [text, setText] = useState('')
  const parse = useParseBooking(tripId)
  const result = parse.data
  const masked = result
    ? MASKED_ORDER.filter((k) => result.masked[k]).map((k) => `${k} ${result.masked[k]}개`)
    : []

  return (
    <BottomSheet open title="예약 메일로 입력" onClose={onClose}>
      <div className="space-y-3">
        <p className="text-sm text-gray-600">
          항공권·숙소 예약 확인 메일 내용을 붙여넣으세요. 카드번호·여권번호·생년월일·연락처는 AI에
          보내기 전에 가리고, 붙여넣은 내용은 저장하지 않습니다.
        </p>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={8}
          maxLength={20000}
          placeholder="예약 확인 메일 전체를 붙여넣기"
          className="w-full rounded-lg border border-gray-300 p-3 text-base"
          aria-label="예약 메일 내용"
        />
        <button
          type="button"
          disabled={text.trim().length < 20 || parse.isPending}
          onClick={() => parse.mutate(text)}
          className={`${BTN.ai} w-full`}
        >
          {parse.isPending ? 'AI가 읽는 중…' : 'AI로 읽기'}
        </button>
        {parse.isPending && (
          <LoadingBlock
            tone="ai"
            title="Claude가 메일을 읽는 중…"
            hint="30초쯤 걸립니다"
            rows={1}
          />
        )}
        {parse.error && <p className="text-sm text-red-700">{parse.error.message}</p>}
        {result && (
          <div className={`${PANEL.ai} space-y-2 p-3 text-sm`}>
            <p className="flex items-center gap-2 font-semibold">
              {result.kind === 'flight'
                ? `항공편 ${result.flight?.legs.length ?? 0}구간을 찾았습니다`
                : result.kind === 'stay'
                  ? `숙소 "${result.stay?.name}"을(를) 찾았습니다`
                  : '예약 내용을 찾지 못했습니다'}
              <span className={BADGE.ai}>AI 제안</span>
            </p>
            {result.note && <p className="text-amber-800">⚠ {result.note}</p>}
            {masked.length > 0 && (
              <p className="text-xs text-gray-500">가린 정보: {masked.join(', ')}</p>
            )}
            {result.kind !== 'none' && (
              <button
                type="button"
                onClick={() => onResult(result)}
                className={`${BTN.primary} w-full`}
              >
                {result.kind === 'flight' ? '항공편 입력에서 확인하기' : '숙소 입력에서 확인하기'}
              </button>
            )}
            <p className="text-[11px] text-gray-500">
              저장하기 전에 다음 화면에서 내용을 꼭 확인하세요.
              {result.kind === 'stay' ? ' 숙소 위치는 검색해서 골라야 합니다.' : ''}
            </p>
          </div>
        )}
      </div>
    </BottomSheet>
  )
}
