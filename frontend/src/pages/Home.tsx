import { useState } from 'react'
import { Link } from 'react-router'
import { useCities, useCreateTrip } from '../api/hooks'
import { BottomSheet } from '../components/BottomSheet'
import { dDay } from '../lib/format'
import { todayIso, useCurrentTrip } from '../lib/trip'
import { Page } from '../components/MapLayout'

const inputClass = 'min-h-11 w-full rounded-lg border border-gray-300 px-3 text-base'

function CreateTripForm({ onDone }: { onDone: (id: number) => void }) {
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

export function Home() {
  const { trips, trip, setTripId } = useCurrentTrip()
  const [creating, setCreating] = useState(false)
  const today = todayIso()
  const list = trips.data ?? []

  return (
    <Page>
      <div className="flex items-center gap-3">
        <img src="/icon.svg" alt="" className="size-10 rounded-xl" />
        <div className="flex-1">
          <h1 className="text-xl font-bold">dongseon</h1>
          <p className="text-sm text-gray-500">가고 싶은 곳을 모아 날짜별 동선으로</p>
        </div>
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="min-h-11 rounded-lg bg-teal-700 px-4 text-sm font-semibold text-white"
        >
          + 새 여행
        </button>
      </div>

      {trip && (
        <Link to="/places" className="block rounded-xl border border-teal-200 bg-teal-50 p-4">
          <p className="text-sm text-teal-800">
            {trip.start_date <= today && today <= trip.end_date
              ? '여행 중'
              : dDay(trip.start_date, today)}
          </p>
          <p className="text-lg font-bold">{trip.title}</p>
          <p className="text-sm text-gray-600">
            {trip.city_name} · {trip.start_date} ~ {trip.end_date} · 장소 {trip.pin_count}곳
          </p>
        </Link>
      )}

      {trips.isSuccess && list.length === 0 && (
        <p className="rounded-xl border border-dashed border-gray-300 bg-white p-4 text-gray-500">
          아직 여행이 없습니다. '+ 새 여행'으로 시작하세요.
        </p>
      )}

      {list.length > 1 && (
        <div>
          <h2 className="mb-2 text-sm font-semibold text-gray-600">모든 여행</h2>
          <ul className="divide-y divide-gray-200 rounded-xl border border-gray-200 bg-white">
            {list.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => setTripId(t.id)}
                  className="flex min-h-14 w-full items-center justify-between px-4 py-2 text-left"
                >
                  <span>
                    <span className="block font-medium">{t.title}</span>
                    <span className="block text-xs text-gray-500">
                      {t.city_name} · {t.start_date} ~ {t.end_date}
                    </span>
                  </span>
                  {t.id === trip?.id && <span className="text-sm text-teal-700">선택됨</span>}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <BottomSheet open={creating} title="새 여행" onClose={() => setCreating(false)}>
        <CreateTripForm
          onDone={(id) => {
            setTripId(id)
            setCreating(false)
          }}
        />
      </BottomSheet>
    </Page>
  )
}
