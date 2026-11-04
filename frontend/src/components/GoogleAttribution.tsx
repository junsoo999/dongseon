/**
 * "Google Maps" text attribution for Google content shown without a Google map
 * (Places policies: Roboto/sans-serif, 400 weight, 12–16px, #5E5E5E, never translated).
 */
export function GoogleAttribution({ className = '' }: { className?: string }) {
  return (
    <span
      translate="no"
      className={`text-xs font-normal text-[#5E5E5E] ${className}`}
      style={{ fontFamily: 'Roboto, Arial, sans-serif' }}
    >
      Google Maps
    </span>
  )
}
