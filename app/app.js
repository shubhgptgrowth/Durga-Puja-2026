/* Pujo Parikrama 2026: a mobile pandal-hopping guide.
 * Data comes from data/guide.json, which the Python pipeline builds. The planner
 * and fitness maths mirror pipeline/geo.py, plan.py and fitness.py so custom
 * plans work offline. */

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (n) => Math.round(n).toLocaleString('en-IN');
const km = (m) => (m / 1000).toFixed(m < 10000 ? 2 : 1);

const store = {
  get(k, d) { try { const v = localStorage.getItem('pp:' + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('pp:' + k, JSON.stringify(v)); } catch { /* private mode */ } },
  clear() { try { Object.keys(localStorage).filter((k) => k.startsWith('pp:')).forEach((k) => localStorage.removeItem(k)); } catch { /* ignore */ } },
};

let G; // the guide bundle
const idx = { pandal: {}, food: {}, parking: {}, transit: {}, zone: {}, day: {} };
const S = {
  view: 'explore', day: null, hour: new Date().getHours(), zone: 'all', sort: 'popular', me: null,
  prefs: store.get('prefs', { height: 165, weight: 65, goal: 10000, lowData: false }),
  checkins: store.get('checkins', {}),   // pandalId -> {ts, how}
  history: store.get('history', {}),     // YYYY-MM-DD -> {m, ms, pandals: [], foods: []}
  car: store.get('car', null),
  plan: store.get('activePlan', null),
  foodZone: 'all', foodF: new Set(), parkZone: 'all',
  layers: store.get('layers', { pandals: true, food: true, parking: false, transit: true }),
  walk: null, watchId: null, wakeLock: null,
};

/* ---------------- maths (mirrors the pipeline) ---------------- */
const R = 6371000, rad = (d) => (d * Math.PI) / 180;
function hav(a, b) {
  const [la1, ln1] = a, [la2, ln2] = b;
  const h = Math.sin(rad(la2 - la1) / 2) ** 2 + Math.cos(rad(la1)) * Math.cos(rad(la2)) * Math.sin(rad(ln2 - ln1) / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
const ll = (r) => [r.lat, r.lng];
const walkM = (a, b) => hav(a, b) * G.meta.model.detour;
const pathLen = (pts) => pts.slice(1).reduce((s, p, i) => s + walkM(pts[i], p), 0);

function orderRoute(start, stops) {
  const n = stops.length;
  if (n <= 1) return [...Array(n).keys()];
  const rem = new Set(stops.keys()); let cur = start; let order = [];
  while (rem.size) {
    let best = null, bd = Infinity;
    for (const i of rem) { const d = hav(cur, stops[i]); if (d < bd) { bd = d; best = i; } }
    order.push(best); rem.delete(best); cur = stops[best];
  }
  const len = (o) => pathLen([start, ...o.map((i) => stops[i])]);
  let bestLen = len(order), improved = true;
  while (improved) {
    improved = false;
    for (let i = 0; i < n - 1; i++) for (let j = i + 1; j < n; j++) {
      const c = [...order.slice(0, i), ...order.slice(i, j + 1).reverse(), ...order.slice(j + 1)];
      const cl = len(c);
      if (cl < bestLen - 1e-6) { order = c; bestLen = cl; improved = true; }
    }
  }
  return order;
}

const crowdIndex = (base, dayFactor, hour) => Math.min(100, Math.round((base / 5) * dayFactor * G.meta.model.hour_factors[((hour % 24) + 24) % 24] * 100));
const stride = () => (S.prefs.height / 100) * G.meta.model.stride_factor;
const stepsFor = (m) => Math.round(m / stride());
const kcalFor = (walkMin, queueMin = 0, brisk = false) =>
  Math.round(((brisk ? G.meta.model.met_brisk : G.meta.model.met_stroll) * S.prefs.weight * walkMin) / 60 + (G.meta.model.queue_met * S.prefs.weight * queueMin) / 60);
const crowdWord = (c) => (c < 25 ? 'Quiet' : c < 50 ? 'Moderate' : c < 75 ? 'Busy' : 'Packed');
const crowdColor = (c) => (c < 25 ? '#16A34A' : c < 50 ? '#CA8A04' : c < 75 ? '#EA580C' : '#DC2626');
const hhmm = (min) => { min = ((Math.round(min) % 1440) + 1440) % 1440; return `${String(Math.floor(min / 60)).padStart(2, '0')}:${String(min % 60).padStart(2, '0')}`; };
const ampm = (h) => `${h % 12 || 12} ${h < 12 ? 'am' : 'pm'}`;
const todayKey = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
const dayFactor = () => idx.day[S.day].factor;
const stars = (n) => '★'.repeat(n) + '☆'.repeat(5 - n);
const zoneOf = (id) => idx.zone[id];

/* ---------------- boot ---------------- */
async function boot() {
  try {
    const res = await fetch('data/guide.json', { cache: 'no-cache' });
    G = await res.json();
  } catch (e) {
    $('#main').innerHTML = `<p class="empty">Couldn't load the guide data. Check your connection and reload.</p>`;
    return;
  }
  const src = { pandal: 'pandals', zone: 'zones', food: 'food', parking: 'parking', transit: 'transit' };
  for (const [k, key] of Object.entries(src)) for (const r of G[key]) idx[k][r.id] = r;
  for (const d of G.meta.days) idx.day[d.id] = d;

  const today = todayKey();
  const todayDay = G.meta.days.find((d) => d.date === today);
  S.day = store.get('day', null) || (todayDay ? todayDay.id : 'saptami');
  if (todayDay) S.day = todayDay.id;

  setupHeader(); setupTabs(); setupExplore(); setupPlan(); setupFood(); setupPark(); setupFit(); setupSheet();
  render();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
  const v = location.hash.slice(1); if (['explore', 'plan', 'food', 'park', 'fit'].includes(v)) go(v);
}

function setupHeader() {
  const sel = $('#daySelect');
  sel.innerHTML = G.meta.days.map((d) => {
    const dt = new Date(d.date + 'T00:00:00');
    return `<option value="${d.id}" title="${dt.toDateString()}">${d.name}</option>`;
  }).join('');
  sel.value = S.day;
  sel.onchange = () => { S.day = sel.value; store.set('day', S.day); render(); };

  const now = new Date(); now.setHours(0, 0, 0, 0);
  const shashthi = new Date(idx.day.shashthi.date + 'T00:00:00');
  const dashami = new Date(idx.day.dashami.date + 'T00:00:00');
  const todayDay = G.meta.days.find((d) => d.date === todayKey());
  const diff = Math.round((shashthi - now) / 864e5);
  $('#countdown').textContent = todayDay ? `Today is ${todayDay.name}. Shubho Pujo! 🙏`
    : now > dashami ? 'Asche bochor abar hobe! See you in 2027'
    : `${diff} day${diff === 1 ? '' : 's'} to Shashthi (17 Oct)`;
}

function setupTabs() {
  $$('.tab').forEach((t) => (t.onclick = () => go(t.dataset.view)));
}
function go(view) {
  S.view = view;
  $$('.tab').forEach((t) => t.classList.toggle('active', t.dataset.view === view));
  $$('.view').forEach((v) => v.classList.toggle('active', v.id === 'view-' + view));
  history.replaceState(null, '', '#' + view);
  window.scrollTo(0, 0);
  if (view === 'explore' && map) setTimeout(() => map.invalidateSize(), 50);
  if (view === 'plan' && planMap) setTimeout(() => planMap.invalidateSize(), 50);
  render();
}
function render() {
  if (S.view === 'explore') renderExplore();
  if (S.view === 'plan') renderItins();
  if (S.view === 'food') renderFood();
  if (S.view === 'park') renderPark();
  if (S.view === 'fit') renderFit();
}

/* ---------------- toast / sheet ---------------- */
let toastT;
function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('show'), 2600);
}
function setupSheet() {
  $('#sheetClose').onclick = closeSheet; $('#sheetBackdrop').onclick = closeSheet;
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSheet(); });
  let y0 = null; const sh = $('#sheet');
  sh.addEventListener('touchstart', (e) => { if (sh.scrollTop <= 0) y0 = e.touches[0].clientY; }, { passive: true });
  sh.addEventListener('touchend', (e) => { if (y0 != null && e.changedTouches[0].clientY - y0 > 90) closeSheet(); y0 = null; });
}
function openSheet(html, onMount) {
  $('#sheetBody').innerHTML = html; $('#sheetBackdrop').hidden = false;
  const s = $('#sheet'); s.scrollTop = 0; s.setAttribute('aria-hidden', 'false');
  requestAnimationFrame(() => s.classList.add('open')); s.focus();
  onMount && onMount($('#sheetBody'));
}
function closeSheet() {
  const s = $('#sheet'); s.classList.remove('open'); s.setAttribute('aria-hidden', 'true'); $('#sheetBackdrop').hidden = true;
}

/* ---------------- maps ---------------- */
let map, planMap, layerGroups = {}, meMarker;
const dark = () => document.documentElement.dataset.theme === 'dark' || (document.documentElement.dataset.theme !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches);
function baseLayer() {
  if (S.prefs.lowData) return null;
  const style = dark() ? 'dark_all' : 'rastertiles/voyager';
  return L.tileLayer(`https://{s}.basemaps.cartocdn.com/${style}/{z}/{x}/{y}{r}.png`, {
    maxZoom: 19, subdomains: 'abcd', detectRetina: true,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  });
}
function makeMap(el) {
  if (!window.L) { el.innerHTML = '<p class="empty">The map is unavailable offline. Lists still work.</p>'; return null; }
  const m = L.map(el, { zoomControl: false, attributionControl: true, tap: true }).setView([22.555, 88.37], 12);
  const b = baseLayer(); if (b) b.addTo(m);
  return m;
}
function pinIcon(color, size, label = '', cls = '') {
  return L.divIcon({ className: '', iconSize: [size, size], iconAnchor: [size / 2, size / 2],
    html: `<div class="pin ${cls}" style="width:${size}px;height:${size}px;background:${color}">${label}</div>` });
}

/* ---------------- EXPLORE ---------------- */
function setupExplore() {
  map = makeMap($('#map'));
  if (map) {
    for (const k of ['pandals', 'food', 'parking', 'transit']) layerGroups[k] = L.layerGroup();
    for (const p of G.pandals) {
      const z = zoneOf(p.zone);
      L.marker(ll(p), { icon: pinIcon(z.color, 14 + p.popularity * 3, p.popularity === 5 ? '★' : ''), title: p.name, riseOnHover: true })
        .on('click', () => pandalSheet(p.id)).addTo(layerGroups.pandals);
    }
    for (const f of G.food) L.marker(ll(f), { icon: pinIcon('#D97706', 20, '🍴', 'sm'), title: f.name }).on('click', () => foodSheet(f.id)).addTo(layerGroups.food);
    for (const p of G.parking) L.marker(ll(p), { icon: pinIcon('#1D4ED8', 20, 'P', 'sq sm'), title: p.name }).on('click', () => parkSheet(p.id)).addTo(layerGroups.parking);
    const lineColor = { blue: '#2563EB', green: '#16A34A', purple: '#9333EA', orange: '#EA580C', suburban: '#57534E' };
    for (const t of G.transit) L.marker(ll(t), { icon: pinIcon(lineColor[t.line], 18, 'M', 'sq sm'), title: t.name }).bindTooltip(t.name).addTo(layerGroups.transit);
    applyLayers();
  }

  $('#zoneChips').innerHTML = [`<button class="chip" data-z="all">All zones</button>`,
    ...G.zones.map((z) => `<button class="chip" data-z="${z.id}"><span class="dot" style="background:${z.color}"></span>${esc(z.short)}</button>`)].join('');
  $('#zoneChips').onclick = (e) => { const b = e.target.closest('[data-z]'); if (!b) return; S.zone = b.dataset.z; fitZone(); renderExplore(); };

  const hr = $('#hourRange'); hr.value = S.hour;
  hr.oninput = () => { S.hour = +hr.value; renderExplore(); };
  $('#sortSelect').onchange = (e) => {
    S.sort = e.target.value;
    if (S.sort === 'near' && !S.me) locate(() => renderExplore()); else renderExplore();
  };
  $('#locateBtn').onclick = () => locate((p) => { map && map.setView(p, 15); renderExplore(); });
  $('#layersBtn').onclick = layersSheet;
  $('#pandalList').onclick = (e) => { const c = e.target.closest('[data-p]'); if (c) pandalSheet(c.dataset.p); };
}
function applyLayers() {
  if (!map) return;
  for (const [k, g] of Object.entries(layerGroups)) S.layers[k] ? g.addTo(map) : g.remove();
}
function layersSheet() {
  const names = { pandals: 'Pandals', food: 'Food', parking: 'Parking', transit: 'Metro & rail' };
  openSheet(`<h2>Map layers</h2><div class="form" style="padding:0;margin-top:12px">${Object.entries(names).map(([k, n]) =>
    `<label class="toggle"><input type="checkbox" data-layer="${k}" ${S.layers[k] ? 'checked' : ''}> <span>${n}</span></label>`).join('')}</div>`,
  (el) => el.onchange = (e) => { const k = e.target.dataset.layer; S.layers[k] = e.target.checked; store.set('layers', S.layers); applyLayers(); });
}
function fitZone() {
  if (!map) return;
  if (S.zone === 'all') map.setView([22.555, 88.37], 12);
  else { const z = zoneOf(S.zone); map.fitBounds(z.bbox, { padding: [30, 30], maxZoom: 16 }); }
}
function locate(cb) {
  if (!navigator.geolocation) return toast("Location isn't available on this device");
  toast('Finding you…');
  navigator.geolocation.getCurrentPosition((pos) => {
    S.me = [pos.coords.latitude, pos.coords.longitude]; drawMe(); cb && cb(S.me);
  }, () => toast("Couldn't get your location"), { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 });
}
function drawMe() {
  if (!map || !S.me) return;
  if (!meMarker) meMarker = L.marker(S.me, { icon: L.divIcon({ className: '', html: '<div class="me-dot"></div>', iconSize: [16, 16] }), zIndexOffset: 1000 }).addTo(map);
  else meMarker.setLatLng(S.me);
}

function renderExplore() {
  $$('#zoneChips .chip').forEach((c) => c.setAttribute('aria-pressed', c.dataset.z === S.zone));
  $('#hourLabel').textContent = `${ampm(S.hour)}, ${idx.day[S.day].name}`;

  const zb = $('#zoneBanner');
  if (S.zone === 'all') zb.innerHTML = '';
  else {
    const z = zoneOf(S.zone), r = z.route, adv = { ok: '🚗 Car OK', limited: '🚗 Limited parking', avoid: '🚇 Leave the car' }[z.car_advisory];
    zb.innerHTML = `<div class="zbox" style="--zc:${z.color}"><h3>${esc(z.name)}</h3><p>${esc(z.vibe)}</p>
      <div class="meta"><span>${z.pandal_ids.length} pandals</span><span>Full loop ${km(r.walk_m)} km</span><span>≈ ${fmt(stepsFor(r.walk_m))} steps</span><span>${adv}</span></div>
      <div class="btn-row" style="margin-top:10px"><button class="btn sm primary" id="zonePlanBtn">Plan this zone</button></div></div>`;
    $('#zonePlanBtn').onclick = () => { presetPlan([S.zone]); };
  }

  let list = G.pandals.filter((p) => S.zone === 'all' || p.zone === S.zone);
  const cr = (p) => crowdIndex(p.crowd_base, dayFactor(), S.hour);
  if (S.sort === 'popular') list.sort((a, b) => b.popularity - a.popularity || cr(a) - cr(b));
  if (S.sort === 'quiet') list.sort((a, b) => cr(a) - cr(b) || b.popularity - a.popularity);
  if (S.sort === 'near' && S.me) list.sort((a, b) => hav(S.me, ll(a)) - hav(S.me, ll(b)));
  $('#listCount').textContent = `${list.length} pandals`;
  $('#pandalList').innerHTML = list.map((p) => pandalCard(p, cr(p))).join('');
}
function pandalCard(p, c) {
  const z = zoneOf(p.zone), dist = S.me ? ` · ${km(hav(S.me, ll(p)))} km away` : '';
  const done = S.checkins[p.id] ? '<span class="tag done">✓ Visited</span>' : '';
  return `<li class="card" data-p="${p.id}">
    <div class="card-top"><div><h3>${esc(p.name)}</h3><div class="zl"><span class="dot" style="background:${z.color}"></span>${esc(z.short)}${dist}</div></div><span class="stars" aria-label="${p.popularity} of 5">${stars(p.popularity)}</span></div>
    <div class="crowd"><span style="min-width:72px">${crowdWord(c)}</span><span class="bar"><i style="width:${Math.max(c, 4)}%;background:${crowdColor(c)}"></i></span><span>Best ${esc(p.best_slot_label)}</span></div>
    <div class="tags">${done}${p.tags.slice(0, 3).map((t) => `<span class="tag">${esc(t)}</span>`).join('')}<span class="tag">🚇 ${esc(p.nearest_metro.name)} · ${p.nearest_metro.walk_min} min</span></div>
  </li>`;
}

function pandalSheet(id) {
  const p = idx.pandal[id], z = zoneOf(p.zone), df = dayFactor();
  const hours = [...Array(24).keys()].map((h) => crowdIndex(p.crowd_base, df, h));
  const quiet = p.quiet_hours[S.day].map(ampm).join(' & ');
  const foods = p.food.map((f) => ({ ...idx.food[f.id], ...f }));
  const parks = p.parking.map((x) => ({ ...idx.parking[x.id], ...x }));
  const visited = S.checkins[p.id];
  openSheet(`
    <div class="zl" style="display:flex;gap:6px;align-items:center;color:var(--ink-3);font-size:13px"><span class="dot" style="width:9px;height:9px;border-radius:50%;background:${z.color}"></span>${esc(z.name)}</div>
    <h2>${esc(p.name)}</h2>
    <div class="stars">${stars(p.popularity)}</div>
    <p class="lead">${esc(p.highlight)}</p>
    <div class="btn-row">
      <a class="btn primary" target="_blank" rel="noopener" href="${dirUrl(ll(p), 'walking')}">Directions</a>
      <button class="btn" id="ciBtn" ${visited ? 'disabled' : ''}>${visited ? '✓ Visited' : 'Check in'}</button>
      <button class="btn" id="mapBtn">Show on map</button>
    </div>
    <h2 class="h2" style="margin:18px 0 4px">Crowd on ${esc(idx.day[S.day].name)}</h2>
    <div class="hours" aria-label="Crowd by hour">${hours.map((c, h) => `<i class="${h === S.hour ? 'now' : ''}" style="height:${Math.max(c, 4)}%;background:${crowdColor(c)}" title="${ampm(h)}: ${crowdWord(c)}"></i>`).join('')}</div>
    <div class="hours-axis"><span>12a</span><span>6a</span><span>12p</span><span>6p</span><span>11p</span></div>
    <dl class="kv">
      <dt>Quietest</dt><dd>${quiet}</dd>
      <dt>Best slot</dt><dd>${esc(p.best_slot_label)}</dd>
      <dt>Time inside</dt><dd>~${p.visit_min} min, plus the queue</dd>
      <dt>Metro</dt><dd><span class="line-${p.nearest_metro.line}">●</span> ${esc(p.nearest_metro.name)}, ${p.nearest_metro.walk_min} min walk</dd>
      ${p.est_year ? `<dt>Since</dt><dd>${p.est_year}</dd>` : ''}
    </dl>
    <h2 class="h2" style="margin:14px 0 4px">Eat nearby</h2>
    <ul class="mini-list">${foods.map((f) => `<li data-food="${f.id}"><span><b>${esc(f.name)}</b><br><small>${esc(f.dishes.slice(0, 2).join(' · '))}</small></span><small>${f.walk_min} min</small></li>`).join('') || '<li>No famous spots nearby. Try the street stalls!</li>'}</ul>
    <h2 class="h2" style="margin:14px 0 4px">Park nearby</h2>
    <ul class="mini-list">${parks.map((x) => `<li data-park="${x.id}"><span><b>${esc(x.name)}</b><br><small>${esc(x.rate_hint)}</small></span><small>${km(x.distance_m)} km</small></li>`).join('') || `<li>No parking nearby. ${esc(z.walk_tip)}</li>`}</ul>
    <p class="fine">Location is approximate. Themes and timings change every year.</p>`,
  (el) => {
    $('#ciBtn', el).onclick = () => { checkin(p.id, 'manual'); pandalSheet(id); render(); };
    $('#mapBtn', el).onclick = () => { closeSheet(); go('explore'); map && map.setView(ll(p), 17); };
    el.querySelectorAll('[data-food]').forEach((li) => (li.onclick = () => foodSheet(li.dataset.food)));
    el.querySelectorAll('[data-park]').forEach((li) => (li.onclick = () => parkSheet(li.dataset.park)));
  });
}

function dirUrl(dest, mode = 'walking') {
  return `https://www.google.com/maps/dir/?api=1&destination=${dest[0]},${dest[1]}&travelmode=${mode}`;
}
/* Google Maps mobile web allows only 3 waypoints, so long routes are split into legs. */
function routeUrls(points) {
  const legs = [];
  for (let i = 0; i < points.length - 1; i += 4) {
    const seg = points.slice(i, i + 5);
    if (seg.length < 2) break;
    const o = seg[0], d = seg[seg.length - 1], w = seg.slice(1, -1);
    legs.push(`https://www.google.com/maps/dir/?api=1&origin=${o[0]},${o[1]}&destination=${d[0]},${d[1]}${w.length ? '&waypoints=' + encodeURIComponent(w.map((p) => p.join(',')).join('|')) : ''}&travelmode=walking`);
  }
  return legs;
}

/* ---------------- PLAN ---------------- */
let planSel = new Set();
function setupPlan() {
  $$('.seg-btn').forEach((b) => (b.onclick = () => {
    $$('.seg-btn').forEach((x) => x.classList.toggle('active', x === b));
    $$('.seg-pane').forEach((p) => p.classList.toggle('active', p.id === 'seg-' + b.dataset.seg));
  }));
  $('#planZones').innerHTML = G.zones.map((z) => `<button type="button" class="chip" data-z="${z.id}"><span class="dot" style="background:${z.color}"></span>${esc(z.short)}</button>`).join('');
  $('#planZones').onclick = (e) => { const b = e.target.closest('[data-z]'); if (!b) return; planSel.has(b.dataset.z) ? planSel.delete(b.dataset.z) : planSel.add(b.dataset.z); syncPlanChips(); };
  const lines = ['blue', 'green', 'purple', 'orange', 'suburban'];
  $('#planStart').innerHTML = `<option value="me">📍 My current location</option>`
    + lines.map((l) => `<optgroup label="${l[0].toUpperCase() + l.slice(1)} line">${G.transit.filter((t) => t.line === l).map((t) => `<option value="t:${t.id}">${esc(t.name)}</option>`).join('')}</optgroup>`).join('')
    + `<optgroup label="Parking">${G.parking.map((p) => `<option value="p:${p.id}">🅿 ${esc(p.name)}</option>`).join('')}</optgroup>`;
  $('#planStart').value = 't:kalighat';
  $('#planForm').onsubmit = (e) => { e.preventDefault(); buildCustom(); };
  $('#itinList').onclick = (e) => { const c = e.target.closest('[data-it]'); if (c) showItin(c.dataset.it); };
  if (S.plan) setTimeout(() => S.view === 'plan' && renderPlanResult(S.plan), 0);
}
function syncPlanChips() { $$('#planZones .chip').forEach((c) => c.setAttribute('aria-pressed', planSel.has(c.dataset.z))); }
function presetPlan(zones, startId) {
  planSel = new Set(zones); syncPlanChips();
  const z = zoneOf(zones[0]);
  $('#planStart').value = 't:' + (startId || z.route.start);
  go('plan'); $('.seg-btn[data-seg="custom"]').click();
  buildCustom();
}

function renderItins() {
  $('#itinList').innerHTML = G.itineraries.map((it) => {
    const t = it.totals, d = idx.day[it.day];
    return `<li class="card" data-it="${it.id}">
      <div class="card-top"><h3>${esc(it.name)}</h3><span class="tag">${esc(d.name)} · ${it.start_time}</span></div>
      <p>${esc(it.blurb)}</p>
      <div class="tags">${it.zones.map((z) => `<span class="tag"><span class="dot" style="display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;background:${zoneOf(z).color}"></span>${esc(zoneOf(z).short)}</span>`).join('')}</div>
      <div class="row"><span>🛕 ${it.pandal_count} pandals</span><span>🚶 ${t.walk_km} km</span><span>👣 ${fmt(stepsFor(t.walk_km * 1000))}</span><span>🔥 ${fmt(kcalFor(t.walk_min, t.dwell_min))} kcal</span><span>⏱ ${Math.floor(t.duration_min / 60)}h ${t.duration_min % 60}m</span></div>
    </li>`;
  }).join('');
}

function showItin(id) {
  const it = G.itineraries.find((x) => x.id === id);
  const segs = it.segments.map((s) => s.type === 'ride'
    ? { type: 'ride', to: idx.transit[s.to_station], depart: s.depart, ride_min: s.ride_min }
    : { type: 'walk', zone: s.zone, start: idx.transit[s.start], stops: s.stops.map((x) => ({ ...x, p: idx.pandal[x.pandal] })) });
  const plan = {
    title: it.name, sub: `${idx.day[it.day].name} · ${it.start_time}–${it.end_time}`, day: it.day, segments: segs,
    totals: { pandals: it.pandal_count, walk_m: it.totals.walk_km * 1000, walk_min: it.totals.walk_min, dwell_min: it.totals.dwell_min, ride_min: it.totals.ride_min, brisk: false },
  };
  S.plan = plan; store.set('activePlan', plan);
  renderPlanResult(plan);
}

function startPoint(val, cb) {
  if (val === 'me') {
    if (S.me) return cb({ id: 'me', name: 'Your location', lat: S.me[0], lng: S.me[1] });
    return locate((p) => cb({ id: 'me', name: 'Your location', lat: p[0], lng: p[1] }));
  }
  const [k, id] = val.split(':');
  const r = k === 't' ? idx.transit[id] : idx.parking[id];
  cb({ id: r.id, name: r.name, lat: r.lat, lng: r.lng });
}

function routeZone(start, pandals, clock, brisk) {
  const pts = pandals.map(ll), order = orderRoute(ll(start), pts);
  const speed = ((brisk ? G.meta.model.walk_kmh_brisk : G.meta.model.walk_kmh_crowd) * 1000) / 60;
  let cur = ll(start), walk = 0, wmin = 0, dwell = 0; const stops = [];
  for (const i of order) {
    const p = pandals[i], d = walkM(cur, pts[i]), w = Math.round(d / speed);
    clock += w;
    const c = crowdIndex(p.crowd_base, dayFactor(), Math.floor(clock / 60));
    const dw = Math.round(p.visit_min * (0.6 + (0.8 * c) / 100));
    stops.push({ pandal: p.id, p, walk_m: Math.round(d), walk_min: w, arrive: hhmm(clock), crowd: c, dwell_min: dw });
    clock += dw; walk += d; wmin += w; dwell += dw; cur = pts[i];
  }
  return { stops, walk, wmin, dwell, clock, end: cur };
}

function entryStation(pandals) {
  let best, bd = Infinity;
  for (const t of G.transit) for (const p of pandals) { const d = hav(ll(t), ll(p)); if (d < bd) { bd = d; best = t; } }
  return best;
}

function planMulti(start, zones, minStars, startMin, brisk, exclude) {
  const groups = zones.map((z) => G.pandals.filter((p) => p.zone === z && p.popularity >= minStars && !exclude.has(p.id))).filter((g) => g.length);
  // Visit zones nearest first.
  const ordered = []; let here = ll(start); const rest = [...groups];
  while (rest.length) {
    rest.sort((a, b) => Math.min(...a.map((p) => hav(here, ll(p)))) - Math.min(...b.map((p) => hav(here, ll(p)))));
    const g = rest.shift(); ordered.push(g); here = ll(g[g.length - 1]);
  }
  let clock = startMin, from = start; const segs = []; let walk = 0, wmin = 0, dwell = 0, ride = 0, n = 0;
  ordered.forEach((g, gi) => {
    const nearest = Math.min(...g.map((p) => hav(ll(from), ll(p))));
    let segStart = from;
    if (nearest > 1800) { // too far to walk, so ride to the zone's entry station
      const st = entryStation(g);
      const rm = Math.round((hav(ll(from), ll(st)) * 1.25) / ((18 * 1000) / 60)) + 10;
      segs.push({ type: 'ride', to: st, depart: hhmm(clock), ride_min: rm });
      clock += rm; ride += rm; segStart = st;
    }
    const r = routeZone(segStart, g, clock, brisk);
    segs.push({ type: 'walk', zone: g[0].zone, start: gi === 0 || segStart !== from ? segStart : null, stops: r.stops });
    clock = r.clock; walk += r.walk; wmin += r.wmin; dwell += r.dwell; n += r.stops.length;
    const last = r.stops[r.stops.length - 1].p; from = { id: last.id, name: last.name, lat: last.lat, lng: last.lng };
  });
  return { segments: segs, totals: { pandals: n, walk_m: walk, walk_min: wmin, dwell_min: dwell, ride_min: ride, brisk }, endMin: clock };
}

function buildCustom() {
  if (!planSel.size) return toast('Pick at least one zone');
  const zones = [...planSel], minStars = +$('#planStars').value, budget = +$('#planBudget').value, brisk = $('#planBrisk').checked;
  const [h, m] = $('#planTime').value.split(':').map(Number), startMin = h * 60 + m;
  startPoint($('#planStart').value, (start) => {
    const exclude = new Set();
    let res = planMulti(start, zones, minStars, startMin, brisk, exclude);
    const total = (r) => r.totals.walk_min + r.totals.dwell_min + r.totals.ride_min;
    // Over budget? Drop the stop that costs the most minutes (detour + dwell) per unit of fame, then re-plan.
    const speed = ((brisk ? G.meta.model.walk_kmh_brisk : G.meta.model.walk_kmh_crowd) * 1000) / 60;
    while (total(res) > budget && res.totals.pandals > 1) {
      const all = res.segments.filter((s) => s.type === 'walk').flatMap((s) => s.stops);
      const pts = [ll(start), ...all.map((x) => ll(x.p))];
      let worst = null, worstScore = -Infinity;
      all.forEach((x, i) => {
        const prev = pts[i], cur = pts[i + 1], next = pts[i + 2];
        const detour = walkM(prev, cur) + (next ? walkM(cur, next) - walkM(prev, next) : 0);
        const score = (detour / speed + x.dwell_min) / x.p.popularity ** 2;
        if (score > worstScore) { worstScore = score; worst = x.pandal; }
      });
      exclude.add(worst);
      res = planMulti(start, zones, minStars, startMin, brisk, exclude);
    }
    if (!res.totals.pandals) return toast('No pandals match. Try lowering the star filter.');
    const plan = {
      title: zones.map((z) => zoneOf(z).short).join(' + '), sub: `${idx.day[S.day].name} · ${hhmm(startMin)}–${hhmm(res.endMin)} from ${start.name}`,
      day: S.day, startPt: start, segments: res.segments, totals: res.totals, skipped: exclude.size,
    };
    S.plan = plan; store.set('activePlan', stripPlan(plan));
    renderPlanResult(plan);
  });
}
const stripPlan = (plan) => JSON.parse(JSON.stringify(plan, (k, v) => (k === 'p' ? undefined : v)));
function hydrate(plan) {
  for (const s of plan.segments) if (s.type === 'walk') for (const x of s.stops) x.p = x.p || idx.pandal[x.pandal];
  return plan;
}

function renderPlanResult(plan) {
  hydrate(plan);
  const box = $('#planResult'); box.hidden = false;
  const t = plan.totals, steps = stepsFor(t.walk_m), kcal = kcalFor(t.walk_min, t.dwell_min, t.brisk);
  const walkSegs = plan.segments.filter((s) => s.type === 'walk');
  const stopsAll = walkSegs.flatMap((s) => s.stops);
  const firstStart = plan.startPt || walkSegs[0].start;
  const pts = [ll(firstStart), ...stopsAll.map((s) => ll(s.p))];
  const legs = routeUrls(pts);

  let n = 0, lastFood = -9; const usedFood = new Set();
  const tl = [`<li class="start"><div class="t">${esc(plan.sub.split('·')[1]?.trim().split('–')[0] || '')}</div><div class="nm">Start at ${esc(firstStart.name)}</div></li>`];
  for (const s of plan.segments) {
    if (s.type === 'ride') { tl.push(`<li class="ride"><div class="t">${s.depart}</div><div class="nm">Metro or cab to ${esc(s.to.name)}</div><div class="sub">~${s.ride_min} min ride</div></li>`); continue; }
    for (const x of s.stops) {
      n++;
      const hour = +x.arrive.slice(0, 2), meal = (hour >= 12 && hour <= 14) || (hour >= 19 && hour <= 21);
      let eat = '';
      const f = x.p.food.filter((ff) => ff.distance_m <= 800).map((ff) => idx.food[ff.id]).find((ff) => !usedFood.has(ff.id));
      if (f && (n - lastFood >= 3 || (meal && n - lastFood >= 2))) { usedFood.add(f.id); lastFood = n; eat = `<div class="eat">🍴 Nearby: ${esc(f.dishes[0])} at ${esc(f.name)}</div>`; }
      const v = S.checkins[x.pandal] ? ' ✓' : '';
      tl.push(`<li data-n="${n}" data-p="${x.pandal}"><div class="t">${x.arrive}</div><div class="nm">${esc(x.p.name)}${v}</div>
        <div class="sub">${x.walk_m ? `${x.walk_m} m walk · ` : ''}${crowdWord(x.crowd)} · ~${x.dwell_min} min inside</div>${eat}</li>`);
    }
  }
  box.innerHTML = `
    <div class="plan-sum">
      <h3>${esc(plan.title)}</h3><div class="fine">${esc(plan.sub)}${plan.skipped ? ` · ${plan.skipped} pandal${plan.skipped > 1 ? 's' : ''} dropped to fit your time` : ''}</div>
      <div class="kpis"><div><b>${t.pandals}</b><span>pandals</span></div><div><b>${km(t.walk_m)}</b><span>km walk</span></div><div><b>${fmt(steps)}</b><span>steps</span></div><div><b>${fmt(kcal)}</b><span>kcal</span></div></div>
      <div class="btn-row">
        <button class="btn primary" id="planWalk">Start walk</button>
        ${legs.map((u, i) => `<a class="btn sm" target="_blank" rel="noopener" href="${u}">Maps${legs.length > 1 ? ` · leg ${i + 1}` : ''}</a>`).join('')}
      </div>
    </div>
    <div id="planMap" class="map short" style="margin:12px 16px;border-radius:16px;overflow:hidden"></div>
    <ol class="timeline">${tl.join('')}</ol>`;
  $('#planWalk').onclick = () => { S.plan = plan; store.set('activePlan', stripPlan(plan)); go('fit'); if (!S.walk) startWalk(); };
  $('.timeline').onclick = (e) => { const li = e.target.closest('[data-p]'); if (li) pandalSheet(li.dataset.p); };

  if (planMap) { planMap.remove(); planMap = null; }
  planMap = makeMap($('#planMap'));
  if (planMap) {
    L.polyline(pts, { color: '#9F1239', weight: 4, opacity: .85, dashArray: '2 8', lineCap: 'round' }).addTo(planMap);
    L.marker(pts[0], { icon: L.divIcon({ className: '', html: '<div class="seq" style="background:#1C1917">▶</div>', iconSize: [26, 26] }) }).addTo(planMap);
    stopsAll.forEach((x, i) => L.marker(ll(x.p), { icon: L.divIcon({ className: '', html: `<div class="seq">${i + 1}</div>`, iconSize: [26, 26] }), title: x.p.name })
      .on('click', () => pandalSheet(x.pandal)).addTo(planMap));
    planMap.fitBounds(L.latLngBounds(pts), { padding: [24, 24] });
  }
  window.scrollTo({ top: box.getBoundingClientRect().top + window.scrollY - $('.topbar').offsetHeight - 8, behavior: 'smooth' });
}

/* ---------------- FOOD ---------------- */
function zoneChipsHtml(sel) {
  return [`<button class="chip" data-z="all" aria-pressed="${sel === 'all'}">All zones</button>`,
    ...G.zones.map((z) => `<button class="chip" data-z="${z.id}" aria-pressed="${sel === z.id}"><span class="dot" style="background:${z.color}"></span>${esc(z.short)}</button>`)].join('');
}
function isOpen(hours, d = new Date()) {
  const [a, b] = hours.split('-').map((x) => { const [h, m] = x.split(':').map(Number); return h * 60 + m; });
  const now = d.getHours() * 60 + d.getMinutes();
  return a <= b ? now >= a && now <= b : now >= a || now <= b;
}
function setupFood() {
  $('#foodZones').onclick = (e) => { const b = e.target.closest('[data-z]'); if (b) { S.foodZone = b.dataset.z; renderFood(); } };
  $('#foodFilters').onclick = (e) => { const b = e.target.closest('[data-f]'); if (!b) return; S.foodF.has(b.dataset.f) ? S.foodF.delete(b.dataset.f) : S.foodF.add(b.dataset.f); renderFood(); };
  $('#foodList').onclick = (e) => { const c = e.target.closest('[data-food]'); if (c) foodSheet(c.dataset.food); };
}
function renderFood() {
  $('#foodZones').innerHTML = zoneChipsHtml(S.foodZone);
  $$('#foodFilters .chip').forEach((c) => c.setAttribute('aria-pressed', S.foodF.has(c.dataset.f)));
  const F = S.foodF;
  const list = G.food.filter((f) => (S.foodZone === 'all' || f.zone === S.foodZone)
    && (!F.has('veg') || f.veg === 'veg') && (!F.has('cheap') || f.price === 1)
    && (!F.has('sweets') || f.type === 'sweets' || f.type === 'drinks') && (!F.has('street') || f.type === 'street')
    && (!F.has('open') || isOpen(f.hours)));
  $('#foodList').innerHTML = list.map((f) => {
    const z = zoneOf(f.zone), near = f.near_pandals.slice(0, 3).map((id) => idx.pandal[id].name);
    const vegDot = f.veg === 'veg' ? '🟢' : f.veg === 'nonveg' ? '🔴' : '🟢🔴';
    return `<li class="card" data-food="${f.id}">
      <div class="card-top"><div><h3>${esc(f.name)}</h3><div class="zl"><span class="dot" style="background:${z.color}"></span>${esc(z.short)} · ${esc(f.type)} · ${'₹'.repeat(f.price)}</div></div><span title="veg / non-veg">${vegDot}</span></div>
      <div class="tags">${f.dishes.map((d) => `<span class="tag">${esc(d)}</span>`).join('')}</div>
      <p>${esc(f.note)}</p>
      <div class="row"><span>${isOpen(f.hours) ? '🟢 Open now' : '⚪ Closed now'} · ${esc(f.hours)}</span>${near.length ? `<span>Near ${esc(near.join(', '))}</span>` : ''}</div>
    </li>`;
  }).join('') || '<li class="empty">Nothing matches these filters.</li>';
}
function foodSheet(id) {
  const f = idx.food[id];
  openSheet(`<h2>${esc(f.name)}</h2><p class="lead">${esc(f.note)}</p>
    <div class="tags">${f.dishes.map((d) => `<span class="tag">${esc(d)}</span>`).join('')}</div>
    <dl class="kv"><dt>Hours</dt><dd>${esc(f.hours)} (puja hours often run later)</dd><dt>Budget</dt><dd>${'₹'.repeat(f.price)}</dd><dt>Diet</dt><dd>${{ veg: 'Pure veg', nonveg: 'Non-veg', both: 'Veg & non-veg' }[f.veg]}</dd></dl>
    <h2 class="h2" style="margin:12px 0 4px">Pandals within walking distance</h2>
    <ul class="mini-list">${f.near_pandals.map((pid) => `<li data-p="${pid}"><b>${esc(idx.pandal[pid].name)}</b><small>${km(hav(ll(f), ll(idx.pandal[pid])))} km</small></li>`).join('') || '<li>None within 800 m</li>'}</ul>
    <div class="btn-row"><a class="btn primary" target="_blank" rel="noopener" href="${dirUrl(ll(f))}">Directions</a><button class="btn" id="ateBtn">I ate here 😋</button></div>`,
  (el) => {
    el.querySelectorAll('[data-p]').forEach((li) => (li.onclick = () => pandalSheet(li.dataset.p)));
    $('#ateBtn', el).onclick = () => { logFood(f.id); toast(`Logged: ${f.name}. Pet pujo done!`); };
  });
}

/* ---------------- PARK ---------------- */
function setupPark() {
  $('#parkZones').onclick = (e) => { const b = e.target.closest('[data-z]'); if (b) { S.parkZone = b.dataset.z; renderPark(); } };
  $('#parkList').onclick = (e) => { const c = e.target.closest('[data-park]'); if (c) parkSheet(c.dataset.park); };
}
function renderPark() {
  const car = S.car;
  $('#carCard').innerHTML = car
    ? `<div class="zbox" style="--zc:#1D4ED8"><h3>🚗 Your car</h3><p>Saved ${new Date(car.ts).toLocaleString('en-IN', { weekday: 'short', hour: 'numeric', minute: '2-digit' })}${S.me ? ` · ${km(hav(S.me, [car.lat, car.lng]))} km from you` : ''}</p>
       <div class="btn-row" style="margin-top:8px"><a class="btn sm primary" target="_blank" rel="noopener" href="${dirUrl([car.lat, car.lng])}">Walk back to car</a><button class="btn sm" id="carClear">Clear</button></div></div>`
    : `<button class="btn block" id="carSave">📍 I parked here: save the spot</button>`;
  if (car) $('#carClear').onclick = () => { S.car = null; store.set('car', null); renderPark(); };
  else $('#carSave').onclick = () => locate((p) => { S.car = { lat: p[0], lng: p[1], ts: Date.now() }; store.set('car', S.car); toast('Car spot saved'); renderPark(); });

  $('#parkZones').innerHTML = zoneChipsHtml(S.parkZone);
  const zs = S.parkZone === 'all' ? G.zones : [zoneOf(S.parkZone)];
  const advLabel = { ok: 'Driving is OK', limited: 'Limited parking', avoid: 'Leave the car behind' };
  $('#parkAdvisory').innerHTML = zs.map((z) => `<div class="adv ${z.car_advisory}" style="margin-top:8px"><b>${esc(z.short)}: ${advLabel[z.car_advisory]}</b><span>${esc(z.walk_tip)}</span></div>`).join('');
  const kindLabel = { mall: 'Mall', multilevel: 'Multi-level', street: 'Street / pay & park', park_ride: 'Park & ride', station: 'Station' };
  const plist = G.parking.filter((p) => S.parkZone === 'all' || p.zone === S.parkZone);
  $('#parkList').innerHTML = plist.map((p) => `<li class="card" data-park="${p.id}">
    <div class="card-top"><div><h3>🅿 ${esc(p.name)}</h3><div class="zl">${esc(kindLabel[p.kind] || p.kind)} · ${esc(p.capacity)} · ${esc(p.rate_hint)}</div></div></div>
    <p>${esc(p.note)}</p></li>`).join('') || '<li class="empty">No listed parking. Use the metro.</li>';
  const near = S.parkZone === 'all' ? G.transit : G.transit.filter((t) => zoneOf(S.parkZone).pandal_ids.some((id) => hav(ll(t), ll(idx.pandal[id])) < 2500));
  $('#transitList').innerHTML = near.map((t) => `<li class="card"><div class="card-top"><b><span class="line-${t.line}">●</span> ${esc(t.name)}</b><small class="fine">${t.line}</small></div></li>`).join('');
}
function parkSheet(id) {
  const p = idx.parking[id];
  const pandals = G.pandals.map((x) => [x, hav(ll(p), ll(x))]).filter(([, d]) => d < 2000).sort((a, b) => a[1] - b[1]).slice(0, 5);
  openSheet(`<h2>🅿 ${esc(p.name)}</h2><p class="lead">${esc(p.note)}</p>
    <dl class="kv"><dt>Type</dt><dd>${esc(p.kind)}</dd><dt>Size</dt><dd>${esc(p.capacity)}</dd><dt>Rate</dt><dd>${esc(p.rate_hint)} (approx.)</dd></dl>
    <h2 class="h2" style="margin:12px 0 4px">Walk to</h2>
    <ul class="mini-list">${pandals.map(([x, d]) => `<li data-p="${x.id}"><b>${esc(x.name)}</b><small>${km(d * G.meta.model.detour)} km</small></li>`).join('') || '<li>Take a cab or the metro onward</li>'}</ul>
    <div class="btn-row"><a class="btn primary" target="_blank" rel="noopener" href="${dirUrl(ll(p), 'driving')}">Drive here</a></div>`,
  (el) => el.querySelectorAll('[data-p]').forEach((li) => (li.onclick = () => pandalSheet(li.dataset.p))));
}

/* ---------------- FIT ---------------- */
const BADGES = [
  { id: 'first', em: '🪔', name: 'Prothom Darshan', desc: 'Visit your first pandal' },
  { id: 'five', em: '🖐️', name: 'Panch Pandal', desc: 'Visit 5 pandals' },
  { id: 'fifteen', em: '🥁', name: 'Dhaki', desc: 'Visit 15 pandals' },
  { id: 'thirty', em: '👑', name: 'Pujo Legend', desc: 'Visit 30 pandals' },
  { id: 'zone', em: '🗺️', name: 'Zone Master', desc: 'Visit every pandal in a zone' },
  { id: 'k10', em: '🏃', name: '10K Pujo', desc: 'Walk 10 km in one day' },
  { id: 'ashtami', em: '🔥', name: 'Ashtami Marathon', desc: '20,000 steps on Ashtami' },
  { id: 'dawn', em: '🌅', name: 'Bhor-er Pakhi', desc: 'Check in between 4 and 7 am' },
  { id: 'owl', em: '🦉', name: 'Raat Jaga', desc: 'Check in between midnight and 4 am' },
  { id: 'foodie', em: '😋', name: 'Pet Pujo', desc: 'Eat at 3 famous spots' },
  { id: 'ns', em: '🧭', name: 'Uttor–Dokkhin', desc: 'North and South on the same day' },
  { id: 'goal', em: '🎯', name: 'Goal Getter', desc: 'Hit your daily step goal' },
];
function earned() {
  const ids = Object.keys(S.checkins), n = ids.length, got = new Set();
  if (n >= 1) got.add('first'); if (n >= 5) got.add('five'); if (n >= 15) got.add('fifteen'); if (n >= 30) got.add('thirty');
  if (G.zones.some((z) => z.pandal_ids.every((id) => S.checkins[id]))) got.add('zone');
  const hours = Object.values(S.checkins).map((c) => new Date(c.ts).getHours());
  if (hours.some((h) => h >= 4 && h < 7)) got.add('dawn');
  if (hours.some((h) => h >= 0 && h < 4)) got.add('owl');
  const foods = new Set(Object.values(S.history).flatMap((d) => d.foods || [])); if (foods.size >= 3) got.add('foodie');
  for (const [date, d] of Object.entries(S.history)) {
    if (d.m >= 10000) got.add('k10');
    if (date === idx.day.ashtami.date && stepsFor(d.m) >= 20000) got.add('ashtami');
    if (stepsFor(d.m) >= S.prefs.goal) got.add('goal');
    const zs = new Set((d.pandals || []).map((id) => idx.pandal[id]?.zone));
    if (zs.has('north') && (zs.has('south_gariahat') || zs.has('south_lakemarket') || zs.has('southwest'))) got.add('ns');
  }
  return got;
}
function dayRec(key = todayKey()) { return (S.history[key] ||= { m: 0, ms: 0, pandals: [], foods: [] }); }
function saveHistory() { store.set('history', S.history); }
function checkin(id, how) {
  if (S.checkins[id]) return false;
  const before = earned();
  S.checkins[id] = { ts: Date.now(), how }; store.set('checkins', S.checkins);
  const d = dayRec(); if (!d.pandals.includes(id)) d.pandals.push(id); saveHistory();
  toast(`✅ Checked in: ${idx.pandal[id].name}`);
  announceBadges(before);
  return true;
}
function logFood(id) { const before = earned(); const d = dayRec(); if (!d.foods.includes(id)) d.foods.push(id); saveHistory(); announceBadges(before); }
function announceBadges(before) {
  const now = earned();
  for (const b of BADGES) if (now.has(b.id) && !before.has(b.id)) setTimeout(() => toast(`${b.em} Badge unlocked: ${b.name}`), 1400);
}

function setupFit() {
  $('#walkBtn').onclick = () => (S.walk ? stopWalk() : startWalk());
  const f = $('#profileForm');
  $('#pHeight').value = S.prefs.height; $('#pWeight').value = S.prefs.weight; $('#pGoal').value = S.prefs.goal; $('#pLowData').checked = S.prefs.lowData;
  f.onsubmit = (e) => {
    e.preventDefault();
    const lowBefore = S.prefs.lowData;
    S.prefs = { height: +$('#pHeight').value || 165, weight: +$('#pWeight').value || 65, goal: +$('#pGoal').value || 10000, lowData: $('#pLowData').checked };
    store.set('prefs', S.prefs); toast('Saved'); renderFit();
    if (lowBefore !== S.prefs.lowData) location.reload();
  };
  $('#resetBtn').onclick = () => { if (confirm('Delete all walks, check-ins and settings on this device?')) { store.clear(); location.reload(); } };
  if (store.get('walking', false)) $('#walkBtn').textContent = 'Resume pujo walk';
}

async function startWalk() {
  if (!navigator.geolocation) return toast("GPS isn't available on this device");
  S.walk = { last: null, startedAt: Date.now() };
  store.set('walking', true);
  S.watchId = navigator.geolocation.watchPosition(onPos, (err) => {
    $('#walkStatus').textContent = err.code === 1 ? 'Location permission was denied. Turn it on in your browser settings to track your walk.' : 'Waiting for GPS…';
  }, { enableHighAccuracy: true, maximumAge: 3000, timeout: 30000 });
  try { S.wakeLock = await navigator.wakeLock?.request('screen'); } catch { /* not supported */ }
  renderFit();
}
function stopWalk() {
  if (S.watchId != null) navigator.geolocation.clearWatch(S.watchId);
  S.watchId = null; S.walk = null; store.set('walking', false);
  try { S.wakeLock?.release(); } catch { /* ignore */ } S.wakeLock = null;
  toast('Walk saved'); renderFit();
}
document.addEventListener('visibilitychange', async () => {
  if (document.visibilityState === 'visible' && S.walk && !S.wakeLock) { try { S.wakeLock = await navigator.wakeLock?.request('screen'); } catch { /* ignore */ } }
});

/* Drop noisy GPS fixes. Implied speeds over 10 km/h mean a vehicle, so those don't count as walking. */
function onPos(pos) {
  const { latitude: lat, longitude: lng, accuracy } = pos.coords;
  S.me = [lat, lng]; drawMe();
  const w = S.walk; if (!w) return;
  if (accuracy > 35) { $('#walkStatus').textContent = `Weak GPS (±${Math.round(accuracy)} m). Waiting for a better fix…`; return; }
  const p = { lat, lng, t: pos.timestamp || Date.now() };
  if (w.last) {
    const d = hav([w.last.lat, w.last.lng], [lat, lng]), dt = (p.t - w.last.t) / 1000;
    if (d < 3 || dt <= 0) return;
    const kmh = (d / dt) * 3.6;
    if (kmh <= 10) { const rec = dayRec(); rec.m += d; rec.ms += Math.min(dt, 120) * 1000; saveHistory(); }
  }
  w.last = p;
  for (const pd of G.pandals) if (!S.checkins[pd.id] && hav([lat, lng], ll(pd)) <= G.meta.model.checkin_radius_m) checkin(pd.id, 'gps');
  for (const f of G.food) if (hav([lat, lng], ll(f)) <= 30) logFood(f.id);
  renderFit();
}

function nextStopText() {
  if (!S.plan) return '';
  hydrate(S.plan);
  const stops = S.plan.segments.filter((s) => s.type === 'walk').flatMap((s) => s.stops);
  const next = stops.find((x) => !S.checkins[x.pandal]);
  if (!next) return '🎉 Plan complete. Every stop visited!';
  const done = stops.length - stops.filter((x) => !S.checkins[x.pandal]).length;
  const dist = S.me ? ` · ${km(walkM(S.me, ll(next.p)))} km` : '';
  return `Plan: ${done}/${stops.length} done · Next up: <b>${esc(next.p.name)}</b>${dist} <a href="${dirUrl(ll(next.p))}" target="_blank" rel="noopener">Directions</a>`;
}

function renderFit() {
  const d = S.history[todayKey()] || { m: 0, ms: 0, pandals: [] };
  const steps = stepsFor(d.m), goal = S.prefs.goal, mins = d.ms / 60000;
  $('#fitSteps').textContent = fmt(steps); $('#fitGoal').textContent = fmt(goal);
  $('#fitKm').textContent = km(d.m); $('#fitKcal').textContent = fmt(kcalFor(mins));
  $('#fitTime').textContent = `${Math.floor(mins / 60)}:${String(Math.floor(mins % 60)).padStart(2, '0')}`;
  $('#fitPandals').textContent = d.pandals.length;
  const C = 2 * Math.PI * 86; $('#ringFg').style.strokeDashoffset = C * (1 - Math.min(1, steps / goal));

  const btn = $('#walkBtn');
  if (S.walk) { btn.classList.add('live'); btn.innerHTML = '<span class="pulse"></span> Tracking · tap to stop'; }
  else { btn.classList.remove('live'); btn.textContent = store.get('walking', false) ? 'Resume pujo walk' : 'Start pujo walk'; }
  const nxt = nextStopText();
  if (S.walk) $('#walkStatus').innerHTML = nxt || 'Tracking. Keep the screen on for the best accuracy.';
  else $('#walkStatus').innerHTML = nxt || "GPS tracking stays on your phone. Pandals check in automatically when you're within 80 m.";

  const got = earned();
  $('#badgeList').innerHTML = BADGES.map((b) => `<li class="badge ${got.has(b.id) ? 'got' : ''}" title="${esc(b.desc)}"><span class="em">${b.em}</span>${esc(b.name)}<br><small class="fine">${esc(b.desc)}</small></li>`).join('');

  const rows = Object.entries(S.history).sort((a, b) => b[0].localeCompare(a[0]));
  const dayName = (date) => G.meta.days.find((x) => x.date === date)?.name;
  $('#historyList').innerHTML = rows.map(([date, r]) => `<li><span><b>${dayName(date) || new Date(date + 'T00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}</b> · ${r.pandals.length} pandals</span><span>${fmt(stepsFor(r.m))} steps · ${km(r.m)} km</span></li>`).join('')
    || '<li><span class="fine">No walks yet. Start one on your first pandal outing.</span></li>';
}

boot();
