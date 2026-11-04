export function Placeholder({ title, milestone }: { title: string; milestone: string }) {
  return (
    <section>
      <h1 className="mb-2 text-xl font-bold">{title}</h1>
      <p className="text-gray-500">{milestone}에서 구현 예정입니다.</p>
    </section>
  )
}
