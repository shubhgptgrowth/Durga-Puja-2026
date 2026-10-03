/* Offline support.
 * - guide.json: network-first, so data fixes reach people during the festival, with the cache as a fallback.
 * - App shell: stale-while-revalidate.
 * - Map tiles and community thumbnails/photos: cache-first, size-capped. This also saves backend egress.
 * - Community API calls (auth, REST, uploads) are never cached. */
const VERSION = 'pp-2026-v10';
const SHELL = ['./', 'index.html', 'styles.css', 'app.js', 'core.js', 'i18n.js', 'config.js', 'state.js', 'ui.js',
  'community.js', 'media.js', 'actions.js', 'sheets.js', 'filters.js', 'pickers.js', 'growth.js', 'radio.js', 'radioCard.js', 'i18n_hi.js', 'data/music.json', 'views/home.js', 'views/explore.js', 'views/plan.js',
  'views/moments.js', 'views/me.js', 'manifest.webmanifest', 'icons/icon.svg', 'icons/icon-192.png', 'data/guide.json',
  'vendor/leaflet/leaflet.css', 'vendor/leaflet/leaflet.js', 'vendor/protomaps-leaflet/protomaps-leaflet.js'];
const TILE_CACHE = 'pp-tiles', TILE_MAX = 800, MEDIA_CACHE = 'pp-media', MEDIA_MAX = 400;
const isTile = (u) => /\/\d+\/\d+\/\d+(@2x)?\.(png|jpg|jpeg|webp|pbf)$/.test(u.pathname);
const isMedia = (u) => u.pathname.includes('/storage/v1/object/public/') || /fonts\.(googleapis|gstatic)\.com$/.test(u.hostname);

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => ![VERSION, TILE_CACHE, MEDIA_CACHE].includes(k)).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

async function trim(name, max) {
  const c = await caches.open(name), keys = await c.keys();
  for (let i = 0; i < keys.length - max; i++) await c.delete(keys[i]);
}
function cacheFirst(e, name, max) {
  e.respondWith(caches.open(name).then(async (c) => {
    const hit = await c.match(e.request);
    if (hit) return hit;
    try {
      const res = await fetch(e.request);
      if (res.ok || res.type === 'opaque') { c.put(e.request, res.clone()); trim(name, max); }
      return res;
    } catch { return new Response('', { status: 504 }); }
  }));
}

/* Vector map tiles: the browser asks for byte ranges of one .pmtiles file. A 206 response can't be put in
 * the Cache API as is, so each range is stored as its own entry (keyed by file + range) and replayed as a
 * 206. The file name carries its build, so ranges from different builds never mix. */
async function pmtilesRange(e) {
  const req = e.request, range = req.headers.get('range');
  if (!range) return fetch(req);
  const c = await caches.open(TILE_CACHE), key = `${req.url}?range=${encodeURIComponent(range)}`;
  const hit = await c.match(key);
  if (hit) {
    const body = await hit.arrayBuffer();
    return new Response(body, { status: 206, headers: { 'Content-Type': 'application/octet-stream', 'Content-Length': String(body.byteLength),
      'Content-Range': hit.headers.get('x-content-range') || '' } });
  }
  const res = await fetch(req);
  if (res.status === 206) {
    const body = await res.clone().arrayBuffer();
    c.put(key, new Response(body, { headers: { 'x-content-range': res.headers.get('content-range') || '' } })).then(() => trim(TILE_CACHE, TILE_MAX));
  }
  return res;
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.pathname.endsWith('.pmtiles')) return e.respondWith(pmtilesRange(e).catch(() => new Response('', { status: 504 })));
  if (url.pathname.endsWith('/tiles/kolkata.json')) return;   // tiny manifest: always ask the network
  if (isMedia(url)) return cacheFirst(e, MEDIA_CACHE, MEDIA_MAX);
  if (url.origin !== location.origin) return isTile(url) ? cacheFirst(e, TILE_CACHE, TILE_MAX) : undefined;

  if (url.pathname.includes('/kit/')) return;   // the team's content kit: always from the network
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
