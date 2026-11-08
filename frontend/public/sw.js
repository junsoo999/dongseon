/* dongseon service worker (hand-written, no build plugin).
 *
 * It keeps only the app shell (index.html, the built /assets/ files, icons) so the app opens without a
 * connection. API responses are never cached here: the app stores its own offline copy (no Google hours,
 * travel times or coordinates) in IndexedDB. Cross-origin requests (Google Maps, tiles, fonts) pass through
 * untouched and are never cached.
 */
const CACHE = 'dongseon-shell-v1'
const STATIC = ['/manifest.webmanifest', '/icon.svg', '/icon-192.png', '/favicon.svg']

function assetsIn(html) {
  return [...new Set([...html.matchAll(/["'](\/assets\/[^"']+)["']/g)].map((m) => m[1]))]
}

/** Store a fresh index.html and its assets; drop assets the new build no longer uses. */
async function refreshShell(response) {
  const cache = await caches.open(CACHE)
  const html = await response.clone().text()
  await cache.put('/', response)
  const wanted = assetsIn(html)
  await Promise.all(
    wanted.map(async (url) => {
      if (!(await cache.match(url))) {
        const r = await fetch(url)
        if (r.ok) await cache.put(url, r)
      }
    }),
  )
  for (const req of await cache.keys()) {
    const path = new URL(req.url).pathname
    if (path.startsWith('/assets/') && !wanted.includes(path)) await cache.delete(req)
  }
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const r = await fetch('/', { cache: 'no-store' })
      if (r.ok) await refreshShell(r)
      const cache = await caches.open(CACHE)
      await Promise.all(
        STATIC.map((u) =>
          fetch(u)
            .then((x) => (x.ok ? cache.put(u, x) : undefined))
            .catch(() => {}),
        ),
      )
      await self.skipWaiting()
    })(),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      for (const key of await caches.keys()) if (key !== CACHE) await caches.delete(key)
      await self.clients.claim()
    })(),
  )
})

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)
  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return

  if (req.mode === 'navigate') {
    // Network first so a new build shows up; the cached shell when offline or the Mac is down.
    event.respondWith(
      (async () => {
        try {
          const r = await fetch(req)
          if (r.ok && (r.headers.get('content-type') || '').includes('text/html')) {
            event.waitUntil(refreshShell(r.clone()))
          }
          if (r.status < 500) return r
        } catch {
          // offline
        }
        return (await caches.match('/')) || Response.error()
      })(),
    )
    return
  }

  if (url.pathname.startsWith('/assets/') || STATIC.includes(url.pathname)) {
    // Built assets have hashed names: cache first.
    event.respondWith(
      (async () => {
        const hit = await caches.match(req)
        if (hit) return hit
        const r = await fetch(req)
        if (r.ok) {
          const copy = r.clone()
          event.waitUntil(caches.open(CACHE).then((c) => c.put(req, copy)))
        }
        return r
      })(),
    )
  }
})
