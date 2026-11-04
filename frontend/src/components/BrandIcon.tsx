import { BRANDS, type Brand } from '../lib/brands'

/** A brand mark in the brand's color, sized like text. */
export function BrandIcon({ brand, className = 'size-5' }: { brand: Brand; className?: string }) {
  const b = BRANDS[brand]
  return (
    <svg viewBox="0 0 24 24" role="img" aria-label={b.title} className={className} fill={b.color}>
      <path d={b.path} />
    </svg>
  )
}
