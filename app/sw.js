/* Offline support.
 * - guide.json: network-first, so data fixes reach people during the festival, with the cache as a fallback.
 * - App shell: stale-while-revalidate.
 * - Map tiles: cache-first, capped at TILE_MAX entries. */
const VERSION = 'pp-2026-v2';
const SHELL = ['./', 'index.html', 'styles.css', 'app.js', 'core.js', 'i18n.js', 'manifest.webmanifest',
  'icons/icon.svg', 'icons/icon-192.png', 'data/guide.json', 'vendor/leaflet/leaflet.css', 'vendor/leaflet/leaflet.js'];
const TILE_CACHE = 'pp-tiles', TILE_MAX = 600;

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION && k !== TILE_CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

async function trimTiles() {
  const c = await caches.open(TILE_CACHE), keys = await c.keys();
  for (let i = 0; i < keys.length - TILE_MAX; i++) await c.delete(keys[i]);
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  if (url.hostname.endsWith('basemaps.cartocdn.com')) {
    e.respondWith(caches.open(TILE_CACHE).then(async (c) => {
      const hit = await c.match(req);
      if (hit) return hit;
      try {
        const res = await fetch(req);
        if (res.ok || res.type === 'opaque') { c.put(req, res.clone()); trimTiles(); }
        return res;
      } catch { return new Response('', { status: 504 }); }
    }));
    return;
  }
  if (url.origin !== location.origin) return;

  if (url.pathname.endsWith('/data/guide.json')) {
    e.respondWith(caches.open(VERSION).then(async (c) => {
      try {
        const res = await fetch(req, { cache: 'no-cache' });
        if (res.ok) c.put('data/guide.json', res.clone());
        return res;
      } catch { return (await c.match('data/guide.json')) || new Response('{}', { status: 503 }); }
    }));
    return;
  }

  e.respondWith(caches.open(VERSION).then(async (c) => {
    const hit = await c.match(req, { ignoreSearch: true });
    const net = fetch(req).then((res) => { if (res.ok) c.put(req, res.clone()); return res; }).catch(() => hit);
    return hit || net;
  }));
});
