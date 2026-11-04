import { useState } from 'react'
import type { FarePrefsIO, FarePrefsOut } from '../api/client'
import { useAirports, useSaveFarePrefs, useStartJob } from '../api/hooks'
import { parseAmount } from '../lib/stays'
import { STOPS_LABEL } from '../lib/farePrefs'
import { BottomSheet } from './BottomSheet'

const HOURS = Array.from({ length: 24 }, (_, i) => i)
const selectClass = 'min-h-11 w-full min-w-0 rounded-lg border border-gray-300 px-2 text-base'

function Stepper({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  onChange: (n: number) => void
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm">{label}</span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          aria-label={`${label} 줄이기`}
          disabled={value <= min}
          onClick={() => onChange(value - 1)}
          className="size-11 rounded-lg border border-gray-300 text-lg disabled:opacity-40"
        >
          −
        </button>
        <span className="w-6 text-center font-medium">{value}</span>
        <button
          type="button"
          aria-label={`${label} 늘리기`}
          disabled={value >= max}
          onClick={() => onChange(value + 1)}
          className="size-11 rounded-lg border border-gray-300 text-lg disabled:opacity-40"
        >
          +
        </button>
      </div>
    </div>
  )
}

function HourRange({
  label,
  from,
  to,
  onChange,
}: {
  label: string
  from: number | null
  to: number | null
  onChange: (f: number | null, t: number | null) => void
}) {
  const opt = (v: number | null, set: (n: number | null) => void, placeholder: string) => (
    <select
      value={v ?? ''}
      onChange={(e) => set(e.target.value === '' ? null : Number(e.target.value))}
      className={selectClass}
    >
      <option value="">{placeholder}</option>
      {HOURS.map((h) => (
        <option key={h} value={h}>
          {h}시
        </option>
      ))}
    </select>
  )
  return (
    <div>
      <p className="mb-1 text-sm text-gray-600">{label}</p>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
        {opt(from, (n) => onChange(n, to), '제한 없음')}
        <span className="text-gray-400">~</span>
        {opt(to, (n) => onChange(from, n), '제한 없음')}
      </div>
    </div>
  )
}

function AirportChips({
  choices,
  value,
  names,
  onChange,
}: {
  choices: string[]
  value: string[]
  names: Record<string, string>
  onChange: (v: string[]) => void
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {choices.map((c) => {
        const on = value.includes(c)
        return (
          <button
            key={c}
            type="button"
            aria-pressed={on}
            onClick={() => onChange(on ? value.filter((x) => x !== c) : [...value, c])}
            className={`min-h-10 rounded-full border px-3 text-sm ${on ? 'border-teal-700 bg-teal-50 font-semibold text-teal-800' : 'border-gray-300'}`}
          >
            {c} {names[c] ?? ''}
          </button>
        )
      })}
    </div>
  )
}

export function FarePrefsSheet({
  tripId,
  prefs,
  onClose,
}: {
  tripId: number
  prefs: FarePrefsOut
  onClose: () => void
}) {
  const airports = useAirports()
  const save = useSaveFarePrefs(tripId)
  const refresh = useStartJob('prices')
  const [p, setP] = useState<FarePrefsIO>(prefs)
  const [price, setPrice] = useState(prefs.max_price_krw ? String(prefs.max_price_krw) : '')
  const [exclude, setExclude] = useState((prefs.airlines_exclude ?? []).join(', '))
  const names = Object.fromEntries((airports.data ?? []).map((a) => [a.code, a.name]))
  const korea = (airports.data ?? []).filter((a) => a.timezone === 'Asia/Seoul').map((a) => a.code)
  const japan = Array.from(
    new Set([
      ...prefs.destinations,
      ...(airports.data ?? []).filter((a) => ['HND', 'NRT'].includes(a.code)).map((a) => a.code),
    ]),
  )
  const priceValue = price.trim() === '' ? null : parseAmount(price)
  const invalid =
    p.origins.length === 0 ||
    p.destinations.length === 0 ||
    (price.trim() !== '' && priceValue === null)

  const submit = () => {
    const body: FarePrefsIO = {
      ...p,
      max_price_krw: priceValue,
      airlines_exclude: exclude
        .split(',')
        .map((x) => x.trim().toUpperCase())
        .filter(Boolean),
    }
    save.mutate(body, {
      onSuccess: () => {
        refresh.mutate()
        onClose()
      },
    })
  }

  return (
    <BottomSheet open title="항공 검색 조건" onClose={onClose}>
      <div className="space-y-5">
        <div className="space-y-2">
          <Stepper
            label="성인"
            value={p.adults}
            min={1}
            max={9}
            onChange={(n) => setP({ ...p, adults: n })}
          />
          <Stepper
            label="어린이"
            value={p.children ?? 0}
            min={0}
            max={8}
            onChange={(n) => setP({ ...p, children: n })}
          />
        </div>
        <div>
          <p className="mb-2 text-sm text-gray-600">출발 공항</p>
          <AirportChips
            choices={korea.length ? korea : prefs.airport_choices}
            value={p.origins}
            names={names}
            onChange={(v) => setP({ ...p, origins: v })}
          />
        </div>
        <div>
          <p className="mb-2 text-sm text-gray-600">도착 공항</p>
          <AirportChips
            choices={japan}
            value={p.destinations}
            names={names}
            onChange={(v) => setP({ ...p, destinations: v })}
          />
        </div>
        <div>
          <p className="mb-2 text-sm text-gray-600">경유</p>
          <div className="grid grid-cols-3 gap-2">
            {[0, 1, null].map((n) => (
              <button
                key={String(n)}
                type="button"
                aria-pressed={p.max_stops === n}
                onClick={() => setP({ ...p, max_stops: n })}
                className={`min-h-11 rounded-lg border text-sm ${p.max_stops === n ? 'border-teal-700 bg-teal-50 font-semibold text-teal-800' : 'border-gray-300'}`}
              >
                {STOPS_LABEL(n)}
              </button>
            ))}
          </div>
        </div>
        <HourRange
          label="가는 편 출발 시각 (현지)"
          from={p.out_dep_from ?? null}
          to={p.out_dep_to ?? null}
          onChange={(f, t) => setP({ ...p, out_dep_from: f, out_dep_to: t })}
        />
        <HourRange
          label="오는 편 출발 시각 (현지)"
          from={p.back_dep_from ?? null}
          to={p.back_dep_to ?? null}
          onChange={(f, t) => setP({ ...p, back_dep_from: f, back_dep_to: t })}
        />
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm">
            <span className="mb-1 block text-gray-600">위탁 수하물 (일행 전체)</span>
            <select
              value={p.checked_bags ?? 0}
              onChange={(e) => setP({ ...p, checked_bags: Number(e.target.value) || null })}
              className={selectClass}
            >
              <option value={0}>상관없음</option>
              {[1, 2, 3, 4].map((n) => (
                <option key={n} value={n}>
                  {n}개 포함
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-gray-600">최대 가격 (원, 일행 합계)</span>
            <input
              inputMode="numeric"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="제한 없음"
              className={selectClass}
            />
          </label>
        </div>
        <label className="block text-sm">
          <span className="mb-1 block text-gray-600">제외할 항공사 코드 (쉼표로 구분)</span>
          <input
            value={exclude}
            onChange={(e) => setExclude(e.target.value)}
            placeholder="예: 7C, TW"
            className={selectClass}
          />
        </label>
        {save.error && <p className="text-sm text-red-700">{save.error.message}</p>}
        <button
          type="button"
          disabled={invalid || save.isPending}
          onClick={submit}
          className="min-h-11 w-full rounded-lg bg-teal-700 font-semibold text-white disabled:opacity-50"
        >
          {save.isPending ? '저장 중…' : '저장하고 다시 검색'}
        </button>
        <p className="text-xs text-gray-500">검색 한 번에 공항 조합마다 Ignav 요청 1회를 씁니다.</p>
      </div>
    </BottomSheet>
  )
}
