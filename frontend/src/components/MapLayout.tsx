import type { ReactNode } from 'react'

/**
 * Map screens: a large rounded map with a side panel on wide screens; on phones the map sits on top and the
 * panel slides over its bottom edge like a sheet.
 */
export function MapLayout({ map, children }: { map: ReactNode; children: ReactNode }) {
  return (
    <div className="md:flex md:h-full md:gap-4 md:p-4">
      <div className="h-[46dvh] overflow-hidden md:h-auto md:min-w-0 md:flex-1 md:rounded-2xl md:border md:border-gray-200 md:shadow-sm">
        {map}
      </div>
      <div className="relative z-10 -mt-5 rounded-t-3xl bg-gray-50 px-4 pt-3 pb-6 shadow-[0_-4px_16px_rgba(0,0,0,0.06)] md:mt-0 md:w-[440px] md:shrink-0 md:overflow-y-auto md:rounded-2xl md:border md:border-gray-200 md:bg-white md:p-5 md:shadow-sm">
        <div aria-hidden className="mx-auto mb-3 h-1 w-10 rounded-full bg-gray-300 md:hidden" />
        <div className="space-y-4">{children}</div>
      </div>
    </div>
  )
}

/** Regular screens: a centered column with comfortable padding. */
export function Page({ children }: { children: ReactNode }) {
  return <div className="mx-auto max-w-3xl space-y-5 px-4 py-5 md:py-8">{children}</div>
}
