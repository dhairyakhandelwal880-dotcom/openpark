/* OpenPark Autonomous Offline Service Worker Engine v1.0
   Enables 100% offline self-contained launch, precaching, tile persistence & API fallbacks.
*/

const CACHE_NAME = 'openpark-offline-v1';
const PRECACHE_ASSETS = [
  '/app/',
  '/app/index.html',
  '/app/manifest.json',
  '/app/css/ui-polish.css',
  '/app/js/ui-polish.js',
  '/app/js/animated-list.js',
  '/app/js/target-cursor.js',
  '/app/js/jelly-radio.js',
  '/app/vendor/maplibre-gl.js',
  '/app/vendor/maplibre-gl.css',
  '/app/vendor/gsap.min.js',
  '/app/vendor/fonts/fonts.css',
  '/app/vendor/fonts/inter-400.woff2',
  '/app/vendor/fonts/inter-600.woff2',
  '/app/vendor/fonts/inter-700.woff2',
  '/app/vendor/fonts/jetbrains-mono-400.woff2',
  '/app/vendor/fonts/jetbrains-mono-700.woff2'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[OpenPark SW] Precaching core offline mobility assets...');
      return cache.addAll(PRECACHE_ASSETS).catch((err) => {
        console.warn('[OpenPark SW] Precache warning, caching individually:', err);
        return Promise.all(
          PRECACHE_ASSETS.map((url) =>
            cache.add(url).catch((e) => console.warn('[OpenPark SW] Failed to cache', url, e))
          )
        );
      });
    })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            console.log('[OpenPark SW] Purging obsolete cache:', key);
            return caches.delete(key);
          }
        })
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // 1. Navigation requests (e.g. visiting /app/) -> Serve cached index.html if offline
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(async () => {
        const cache = await caches.open(CACHE_NAME);
        return (await cache.match('/app/index.html')) || (await cache.match('/app/'));
      })
    );
    return;
  }

  // 2. Map Tiles (Carto, OSM, Google Hybrid) -> Cache-first with offline persistence
  if (
    url.hostname.includes('cartocdn.com') ||
    url.hostname.includes('openstreetmap.org') ||
    url.hostname.includes('google.com') && url.pathname.includes('/vt')
  ) {
    event.respondWith(
      caches.open(CACHE_NAME).then(async (cache) => {
        const cached = await cache.match(req);
        if (cached) return cached;
        try {
          const res = await fetch(req);
          if (res && res.status === 200) {
            cache.put(req, res.clone());
          }
          return res;
        } catch (e) {
          // If offline and tile not cached, return transparent 1x1 fallback png
          return new Response(
            new Uint8Array([
              137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 13, 73, 72, 68, 82, 0, 0, 0, 1, 0, 0, 0, 1, 8, 6, 0, 0, 0, 31, 21, 196, 137, 0, 0, 0, 10, 73, 68, 65, 84, 120, 156, 99, 0, 1, 0, 0, 5, 0, 1, 13, 10, 45, 180, 0, 0, 0, 0, 73, 69, 78, 68, 174, 66, 96, 130
            ]),
            { headers: { 'Content-Type': 'image/png' } }
          );
        }
      })
    );
    return;
  }

  // 3. Static local assets (CSS, JS, Fonts, Vendor) -> Stale-While-Revalidate
  if (url.origin === self.location.origin && url.pathname.startsWith('/app/')) {
    event.respondWith(
      caches.match(req).then((cached) => {
        const fetchPromise = fetch(req)
          .then((networkRes) => {
            if (networkRes && networkRes.status === 200) {
              const clone = networkRes.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
            }
            return networkRes;
          })
          .catch(() => cached);
        return cached || fetchPromise;
      })
    );
    return;
  }

  // 4. API Endpoints fallback when offline
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(req).catch(() => {
        if (url.pathname.includes('/parking/lots')) {
          return new Response(JSON.stringify({
            status: 'offline',
            offline: true,
            lots: []
          }), { headers: { 'Content-Type': 'application/json' } });
        }
        if (url.pathname.includes('/traccar/route')) {
          return new Response(JSON.stringify({
            status: 'offline',
            source: 'offline_service_worker'
          }), { headers: { 'Content-Type': 'application/json' } });
        }
        return new Response(JSON.stringify({ status: 'offline', offline: true }), {
          headers: { 'Content-Type': 'application/json' }
        });
      })
    );
    return;
  }

  // Default: Network with cache fallback
  event.respondWith(
    fetch(req).catch(() => caches.match(req))
  );
});
