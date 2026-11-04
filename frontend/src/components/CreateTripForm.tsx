import { useState } from 'react'
import { useCities, useCreateTrip } from '../api/hooks'

const inputClass = 'min-h-11 w-full rounded-lg border border-gray-300 px-3 text-base'

export function CreateTripForm({ onDone }: { onDone: (id: number) => void }) {
  const cities = useCities()
  const create = useCreateTrip()
  const [title, setTitle] = useState('')
  const [city, setCity] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const cityKey = city || cities.data?.[0]?.key || ''
  const valid = title.trim() && cityKey && start && end && end >= start

  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault()
        if (!valid) return
        create.mutate(
          {
            title: title.trim(),
            city_key: cityKey,
            start_date: start,
            end_date: end,
            pace: 'normal',
          },
          { onSuccess: (t) => onDone(t.id) },
        )
      }}
    >
      <label className="block text-sm">
        <span className="mb-1 block text-gray-600">여행 이름</span>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={100}
          className={inputClass}
        />
      </label>
      <label className="block text-sm">
        <span className="mb-1 block text-gray-600">도시</span>
        <select value={cityKey} onChange={(e) => setCity(e.target.value)} className={inputClass}>
          {(cities.data ?? []).map((c) => (
            <option key={c.key} value={c.key}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      <div className="grid grid-cols-2 gap-3">
        <label className="block text-sm">
          <span className="mb-1 block text-gray-600">출발일</span>
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className={inputClass}
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-gray-600">돌아오는 날</span>
          <input
            type="date"
            value={end}
            min={start}
            onChange={(e) => setEnd(e.target.value)}
            className={inputClass}
          />
        </label>
      </div>
      {create.error && <p className="text-sm text-red-700">{create.error.message}</p>}
      <button
        type="submit"
        disabled={!valid || create.isPending}
        className="min-h-11 w-full rounded-lg bg-teal-700 font-semibold text-white disabled:opacity-50"
      >
        {create.isPending ? '만드는 중…' : '여행 만들기'}
      </button>
    </form>
  )
}
