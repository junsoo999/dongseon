export function Home() {
  return (
    <section>
      <div className="mb-4 flex items-center gap-3">
        <img src="/icon.svg" alt="" className="size-10 rounded-xl" />
        <div>
          <h1 className="text-xl font-bold">dongseon</h1>
          <p className="text-sm text-gray-500">가고 싶은 곳을 모아 날짜별 동선으로</p>
        </div>
      </div>
      <p className="rounded-xl border border-dashed border-gray-300 bg-white p-4 text-gray-500">
        아직 여행이 없습니다. 여행 만들기는 M1에서 추가됩니다.
      </p>
    </section>
  )
}
