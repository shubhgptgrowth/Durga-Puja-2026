/* Pujo Parikrama 2026: a mobile pandal-hopping guide.
 * Data comes from data/guide.json, which the Python pipeline builds. The pure maths
 * (routing, crowd, fitness, GPS filtering, step detection) lives in core.js, and
 * tests/js checks it against the pipeline. */

import {
  hav, orderRoute, crowdIndex as crowdCore, strideM, kcalFor as kcalCore, judgeFix, StepDetector,
  routeUrls, isOpen, hhmm, encodePlan, decodePlan,
} from './core.js';
import { makeT } from './i18n.js';

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
const DEFAULT_PREFS = { height: 165, weight: 65, goal: 10000, lowData: false, motion: true, lang: 'en' };
const S = {
  view: 'explore', day: null, hour: new Date().getHours(), zone: 'all', sort: 'popular', me: null,
  prefs: { ...DEFAULT_PREFS, ...store.get('prefs', {}) },
  checkins: store.get('checkins', {}),   // pandalId -> {ts, how}
  history: store.get('history', {}),     // YYYY-MM-DD -> {m, ms, steps, pandals: [], foods: []}
  car: store.get('car', null),
  plan: store.get('activePlan', null),
  foodZone: 'all', foodF: new Set(), parkZone: 'all',
  layers: store.get('layers', { pandals: true, food: true, parking: false, transit: true }),
  walk: null, watchId: null, wakeLock: null, detector: null, lastMotion: 0,
};
const t = makeT(() => S.prefs.lang);
const bn = () => S.prefs.lang === 'bn';

/* ---------------- model helpers ---------------- */
const ll = (r) => [r.lat, r.lng];
const M = () => G.meta.model;
const walkM = (a, b) => hav(a, b) * M().detour;
const crowdIndex = (base, df, hour) => crowdCore(M().hour_factors, base, df, hour);
const stride = () => strideM(S.prefs.height, M().stride_factor);
const stepsFor = (m) => Math.round(m / stride());
const kcalFor = (walkMin, queueMin = 0, brisk = false) =>
  kcalCore({ walkMin, queueMin, weightKg: S.prefs.weight, met: brisk ? M().met_brisk : M().met_stroll, queueMet: M().queue_met });
const crowdWord = (c) => t('crowd.' + (c < 25 ? 0 : c < 50 ? 1 : c < 75 ? 2 : 3));
const crowdColor = (c) => (c < 25 ? '#16A34A' : c < 50 ? '#CA8A04' : c < 75 ? '#EA580C' : '#DC2626');
function ampm(h) {
  h = ((h % 24) + 24) % 24;
  if (!bn()) return `${h % 12 || 12} ${h < 12 ? 'am' : 'pm'}`;
  const part = h < 4 ? 'রাত' : h < 6 ? 'ভোর' : h < 12 ? 'সকাল' : h < 16 ? 'দুপুর' : h < 18 ? 'বিকেল' : h < 20 ? 'সন্ধে' : 'রাত';
  return `${part} ${h % 12 || 12}টা`;
}
const todayKey = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
const dayFactor = () => idx.day[S.day].factor;
const stars = (n) => '★'.repeat(n) + '☆'.repeat(5 - n);
const zoneOf = (id) => idx.zone[id];
const nm = (p) => (bn() && p.name_bn) || p.name;
const zn = (z) => (bn() && z.name_bn) || z.name;
const zs = (z) => (bn() && z.short_bn) || z.short;
const dn = (d) => (bn() && d.name_bn) || d.name;
const btn = (attrs) => `role="button" tabindex="0" ${attrs}`;

/* ---------------- boot ---------------- */
async function boot() {
  try {
    const res = await fetch('data/guide.json', { cache: 'no-cache' });
    G = await res.json();
  } catch {
    $('#main').innerHTML = `<p class="empty">${t('load.fail')}</p>`;
    return;
  }
  const src = { pandal: 'pandals', zone: 'zones', food: 'food', parking: 'parking', transit: 'transit' };
  for (const [k, key] of Object.entries(src)) for (const r of G[key]) idx[k][r.id] = r;
  for (const d of G.meta.days) idx.day[d.id] = d;

  const prevVersion = store.get('dataVersion', null);
  if (prevVersion && prevVersion !== G.meta.version) setTimeout(() => toast(t('data.updated')), 800);
  store.set('dataVersion', G.meta.version);

  const todayDay = G.meta.days.find((d) => d.date === todayKey());
  S.day = todayDay ? todayDay.id : store.get('day', null) || 'saptami';

  setupHeader(); setupTabs(); setupExplore(); setupPlan(); setupFood(); setupPark(); setupFit(); setupSheet(); setupA11y();
  applyStatic();

  const hash = location.hash.slice(1);
  if (hash.startsWith('plan=')) openSharedPlan(decodePlan(hash.slice(5)));
  else if (hash.startsWith('trail=') && G.itineraries.some((i) => i.id === hash.slice(6))) { go('plan'); showItin(hash.slice(6)); toast(t('share.loaded')); }
  else if (['explore', 'plan', 'food', 'park', 'fit'].includes(hash)) go(hash);
  else render();

  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
  addEventListener('offline', () => toast(t('net.off')));
  addEventListener('online', () => toast(t('net.on')));
  if (!navigator.onLine) setTimeout(() => toast(t('net.off')), 600);
}

/* Static text in index.html carries data-i18n keys. */
function applyStatic() {
  document.documentElement.lang = S.prefs.lang;
  $$('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n); });
  $('#langBtn').textContent = t('lang.toggle');
  $('#langBtn').setAttribute('aria-label', t('lang.aria'));
  $('#sheetClose').setAttribute('aria-label', t('sheet.close'));
  $('#parkFine').innerHTML = t('park.fine', { link: `<a href="https://kolkatatrafficpolice.gov.in/" target="_blank" rel="noopener">${t('park.kp')}</a>` });
  fillDaySelect(); fillCountdown(); fillZoneChips(); fillPlanStart();
}

function setupHeader() {
  $('#daySelect').onchange = (e) => { S.day = e.target.value; store.set('day', S.day); render(); };
  $('#langBtn').onclick = () => {
    S.prefs.lang = bn() ? 'en' : 'bn'; store.set('prefs', S.prefs);
    applyStatic(); refreshMapLabels(); render();
    if (S.plan && !$('#planResult').hidden) renderPlanResult(S.plan, false);
  };
}
function fillDaySelect() {
  const sel = $('#daySelect');
  sel.innerHTML = G.meta.days.map((d) => `<option value="${d.id}" title="${new Date(d.date + 'T00:00:00').toDateString()}">${esc(dn(d))}</option>`).join('');
  sel.value = S.day;
}
function fillCountdown() {
  const now = new Date(); now.setHours(0, 0, 0, 0);
  const shashthi = new Date(idx.day.shashthi.date + 'T00:00:00');
  const dashami = new Date(idx.day.dashami.date + 'T00:00:00');
  const todayDay = G.meta.days.find((d) => d.date === todayKey());
  const diff = Math.round((shashthi - now) / 864e5);
  $('#countdown').textContent = todayDay ? t('count.today', { day: dn(todayDay) })
    : now > dashami ? t('count.after')
    : diff === 1 ? t('count.day') : t('count.days', { n: bn() ? String(diff).replace(/\d/g, (c) => '০১২৩৪৫৬৭৮৯'[c]) : diff });
}

function setupTabs() { $$('.tab').forEach((b) => (b.onclick = () => go(b.dataset.view))); }
function go(view) {
  S.view = view;
  $$('.tab').forEach((b) => { b.classList.toggle('active', b.dataset.view === view); b.setAttribute('aria-current', b.dataset.view === view ? 'page' : 'false'); });
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

/* Make role=button elements keyboard-operable. */
function setupA11y() {
  document.addEventListener('keydown', (e) => {
    const el = e.target;
    if ((e.key === 'Enter' || e.key === ' ') && el.getAttribute?.('role') === 'button' && el.tagName !== 'BUTTON') { e.preventDefault(); el.click(); }
  });
}

/* ---------------- toast / sheet ---------------- */
let toastT;
function toast(msg) {
  const el = $('#toast'); el.textContent = msg; el.classList.add('show');
  clearTimeout(toastT); toastT = setTimeout(() => el.classList.remove('show'), 2600);
}
let sheetOpener = null;
function setupSheet() {
  $('#sheetClose').onclick = closeSheet; $('#sheetBackdrop').onclick = closeSheet;
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSheet(); });
  let y0 = null; const sh = $('#sheet');
  sh.addEventListener('touchstart', (e) => { if (sh.scrollTop <= 0) y0 = e.touches[0].clientY; }, { passive: true });
  sh.addEventListener('touchend', (e) => { if (y0 != null && e.changedTouches[0].clientY - y0 > 90) closeSheet(); y0 = null; });
}
function openSheet(html, onMount) {
  if (!$('#sheet').classList.contains('open')) sheetOpener = document.activeElement;
  $('#sheetBody').innerHTML = html; $('#sheetBackdrop').hidden = false;
  const s = $('#sheet'); s.scrollTop = 0; s.setAttribute('aria-hidden', 'false');
  requestAnimationFrame(() => s.classList.add('open')); s.focus();
  onMount && onMount($('#sheetBody'));
}
function closeSheet() {
  const s = $('#sheet');
  if (!s.classList.contains('open')) return;
  s.classList.remove('open'); s.setAttribute('aria-hidden', 'true'); $('#sheetBackdrop').hidden = true;
  sheetOpener?.focus?.(); sheetOpener = null;
}

/* ---------------- maps ---------------- */
let map, planMap, layerGroups = {}, meMarker, pandalMarkers = [];
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
  if (!window.L) { el.innerHTML = `<p class="empty">${t('map.offline')}</p>`; return null; }
  const m = L.map(el, { zoomControl: false, attributionControl: true }).setView([22.555, 88.37], 12);
  const b = baseLayer(); if (b) b.addTo(m);
  return m;
}
function pinIcon(color, size, label = '', cls = '') {
  return L.divIcon({ className: '', iconSize: [size, size], iconAnchor: [size / 2, size / 2],
    html: `<div class="pin ${cls}" style="width:${size}px;height:${size}px;background:${color}">${label}</div>` });
}
function refreshMapLabels() { pandalMarkers.forEach(([mk, p]) => mk.options.title = nm(p)); }

/* ---------------- EXPLORE ---------------- */
function setupExplore() {
  map = makeMap($('#map'));
  if (map) {
    for (const k of ['pandals', 'food', 'parking', 'transit']) layerGroups[k] = L.layerGroup();
    for (const p of G.pandals) {
      const mk = L.marker(ll(p), { icon: pinIcon(zoneOf(p.zone).color, 14 + p.popularity * 3, p.popularity === 5 ? '★' : ''), title: nm(p), riseOnHover: true, keyboard: true })
        .on('click', () => pandalSheet(p.id)).addTo(layerGroups.pandals);
      pandalMarkers.push([mk, p]);
    }
    for (const f of G.food) L.marker(ll(f), { icon: pinIcon('#D97706', 20, '🍴', 'sm'), title: f.name }).on('click', () => foodSheet(f.id)).addTo(layerGroups.food);
    for (const p of G.parking) L.marker(ll(p), { icon: pinIcon('#1D4ED8', 20, 'P', 'sq sm'), title: p.name }).on('click', () => parkSheet(p.id)).addTo(layerGroups.parking);
    const lineColor = { blue: '#2563EB', green: '#16A34A', purple: '#9333EA', orange: '#EA580C', suburban: '#57534E' };
    for (const s of G.transit) L.marker(ll(s), { icon: pinIcon(lineColor[s.line], 18, 'M', 'sq sm'), title: s.name }).bindTooltip(s.name).addTo(layerGroups.transit);
    applyLayers();
  }
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
function fillZoneChips() {
  $('#zoneChips').innerHTML = [`<button class="chip" data-z="all">${t('zones.all')}</button>`,
    ...G.zones.map((z) => `<button class="chip" data-z="${z.id}"><span class="dot" style="background:${z.color}"></span>${esc(zs(z))}</button>`)].join('');
  $('#planZones').innerHTML = G.zones.map((z) => `<button type="button" class="chip" data-z="${z.id}"><span class="dot" style="background:${z.color}"></span>${esc(zs(z))}</button>`).join('');
  syncPlanChips();
}
function applyLayers() {
  if (!map) return;
  for (const [k, g] of Object.entries(layerGroups)) S.layers[k] ? g.addTo(map) : g.remove();
}
function layersSheet() {
  const keys = ['pandals', 'food', 'parking', 'transit'];
  openSheet(`<h2>${t('layers.title')}</h2><div class="form" style="padding:0;margin-top:12px">${keys.map((k) =>
    `<label class="toggle"><input type="checkbox" data-layer="${k}" ${S.layers[k] ? 'checked' : ''}> <span>${t('layers.' + k)}</span></label>`).join('')}</div>`,
  (el) => el.onchange = (e) => { const k = e.target.dataset.layer; S.layers[k] = e.target.checked; store.set('layers', S.layers); applyLayers(); });
}
function fitZone() {
  if (!map) return;
  if (S.zone === 'all') map.setView([22.555, 88.37], 12);
  else map.fitBounds(zoneOf(S.zone).bbox, { padding: [30, 30], maxZoom: 16 });
}
function locate(cb) {
  if (!navigator.geolocation) return toast(t('loc.na'));
  toast(t('loc.finding'));
  navigator.geolocation.getCurrentPosition((pos) => {
    S.me = [pos.coords.latitude, pos.coords.longitude]; drawMe(); cb && cb(S.me);
  }, () => toast(t('loc.fail')), { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 });
}
function drawMe() {
  if (!map || !S.me) return;
  if (!meMarker) meMarker = L.marker(S.me, { icon: L.divIcon({ className: '', html: '<div class="me-dot"></div>', iconSize: [16, 16] }), zIndexOffset: 1000, keyboard: false }).addTo(map);
  else meMarker.setLatLng(S.me);
}

function renderExplore() {
  $$('#zoneChips .chip').forEach((c) => c.setAttribute('aria-pressed', c.dataset.z === S.zone));
  $('#hourLabel').textContent = `${ampm(S.hour)}, ${dn(idx.day[S.day])}`;

  const zb = $('#zoneBanner');
  if (S.zone === 'all') zb.innerHTML = '';
  else {
    const z = zoneOf(S.zone), r = z.route;
    zb.innerHTML = `<div class="zbox" style="--zc:${z.color}"><h3>${esc(zn(z))}</h3><p>${esc(z.vibe)}</p>
      <div class="meta"><span>${t('z.pandals', { n: z.pandal_ids.length })}</span><span>${t('z.loop', { km: km(r.walk_m) })}</span><span>${t('z.steps', { n: fmt(stepsFor(r.walk_m)) })}</span><span>${t('car.' + z.car_advisory)}</span></div>
      <div class="btn-row" style="margin-top:10px"><button class="btn sm primary" id="zonePlanBtn">${t('z.plan')}</button></div></div>`;
    $('#zonePlanBtn').onclick = () => presetPlan([S.zone]);
  }

  const list = G.pandals.filter((p) => S.zone === 'all' || p.zone === S.zone);
  const cr = (p) => crowdIndex(p.crowd_base, dayFactor(), S.hour);
  if (S.sort === 'popular') list.sort((a, b) => b.popularity - a.popularity || cr(a) - cr(b));
  if (S.sort === 'quiet') list.sort((a, b) => cr(a) - cr(b) || b.popularity - a.popularity);
  if (S.sort === 'near' && S.me) list.sort((a, b) => hav(S.me, ll(a)) - hav(S.me, ll(b)));
  $('#listCount').textContent = t('list.count', { n: list.length });
  $('#pandalList').innerHTML = list.map((p) => pandalCard(p, cr(p))).join('');
}
function pandalCard(p, c) {
  const z = zoneOf(p.zone), dist = S.me ? ` · ${t('card.away', { km: km(hav(S.me, ll(p))) })}` : '';
  const done = S.checkins[p.id] ? `<span class="tag done">${t('card.visited')}</span>` : '';
  return `<li class="card" data-p="${p.id}" ${btn(`aria-label="${esc(nm(p))}, ${p.popularity}★, ${crowdWord(c)}"`)}>
    <div class="card-top"><div><h3>${esc(nm(p))}</h3><div class="zl"><span class="dot" style="background:${z.color}"></span>${esc(zs(z))}${dist}</div></div><span class="stars" aria-hidden="true">${stars(p.popularity)}</span></div>
    <div class="crowd"><span style="min-width:72px">${crowdWord(c)}</span><span class="bar"><i style="width:${Math.max(c, 4)}%;background:${crowdColor(c)}"></i></span><span>${t('card.best', { slot: t('slot.' + p.best_slot) })}</span></div>
    <div class="tags">${done}${p.tags.slice(0, 3).map((x) => `<span class="tag">${esc(x)}</span>`).join('')}<span class="tag">🚇 ${esc(p.nearest_metro.name)} · ${p.nearest_metro.walk_min}′</span></div>
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
    <div class="zl" style="display:flex;gap:6px;align-items:center;color:var(--ink-3);font-size:13px"><span class="dot" style="width:9px;height:9px;border-radius:50%;background:${z.color}"></span>${esc(zn(z))}</div>
    <h2>${esc(nm(p))}</h2>
    ${bn() ? `<div class="fine">${esc(p.name)}</div>` : p.name_bn ? `<div class="fine" lang="bn">${esc(p.name_bn)}</div>` : ''}
    <div class="stars" aria-label="${p.popularity} / 5">${stars(p.popularity)}</div>
    <p class="lead">${esc(p.highlight)}</p>
    <div class="btn-row">
      <a class="btn primary" target="_blank" rel="noopener" href="${dirUrl(ll(p), 'walking')}">${t('p.directions')}</a>
      <button class="btn" id="ciBtn" ${visited ? 'disabled' : ''}>${visited ? t('p.visited') : t('p.checkin')}</button>
      <button class="btn" id="mapBtn">${t('p.showmap')}</button>
    </div>
    <h2 class="h2">${t('p.crowdOn', { day: dn(idx.day[S.day]) })}</h2>
    <div class="hours" role="img" aria-label="${t('p.crowdChart')}">${hours.map((c, h) => `<i class="${h === S.hour ? 'now' : ''}" style="height:${Math.max(c, 4)}%;background:${crowdColor(c)}" title="${ampm(h)}: ${crowdWord(c)}"></i>`).join('')}</div>
    <div class="hours-axis" aria-hidden="true"><span>12a</span><span>6a</span><span>12p</span><span>6p</span><span>11p</span></div>
    <dl class="kv">
      <dt>${t('p.quietest')}</dt><dd>${quiet}</dd>
      <dt>${t('p.bestslot')}</dt><dd>${t('slot.' + p.best_slot)}</dd>
      <dt>${t('p.inside')}</dt><dd>${t('p.insideV', { n: p.visit_min })}</dd>
      <dt>${t('p.metro')}</dt><dd><span class="line-${p.nearest_metro.line}">●</span> ${t('p.metroV', { name: esc(p.nearest_metro.name), n: p.nearest_metro.walk_min })}</dd>
      ${p.est_year ? `<dt>${t('p.since')}</dt><dd>${p.est_year}</dd>` : ''}
    </dl>
    <h2 class="h2">${t('p.eat')}</h2>
    <ul class="mini-list">${foods.map((f) => `<li data-food="${f.id}" ${btn('')}><span><b>${esc(f.name)}</b><br><small>${esc(f.dishes.slice(0, 2).join(' · '))}</small></span><small>${f.walk_min}′</small></li>`).join('') || `<li>${t('p.noeat')}</li>`}</ul>
    <h2 class="h2">${t('p.park')}</h2>
    <ul class="mini-list">${parks.map((x) => `<li data-park="${x.id}" ${btn('')}><span><b>${esc(x.name)}</b><br><small>${esc(x.rate_hint)}</small></span><small>${km(x.distance_m)} km</small></li>`).join('') || `<li>${t('p.nopark')} ${esc(z.walk_tip)}</li>`}</ul>
    <p class="fine">${t('p.disclaimer')}</p>`,
  (el) => {
    $('#ciBtn', el).onclick = () => { checkin(p.id, 'manual'); pandalSheet(id); render(); };
    $('#mapBtn', el).onclick = () => { closeSheet(); go('explore'); map && map.setView(ll(p), 17); };
    el.querySelectorAll('[data-food]').forEach((li) => (li.onclick = () => foodSheet(li.dataset.food)));
    el.querySelectorAll('[data-park]').forEach((li) => (li.onclick = () => parkSheet(li.dataset.park)));
  });
}
const dirUrl = (dest, mode = 'walking') => `https://www.google.com/maps/dir/?api=1&destination=${dest[0]},${dest[1]}&travelmode=${mode}`;

/* ---------------- PLAN ---------------- */
let planSel = new Set();
function setupPlan() {
  $$('.seg-btn').forEach((b) => (b.onclick = () => selectSeg(b.dataset.seg)));
  $('#planZones').onclick = (e) => { const b = e.target.closest('[data-z]'); if (!b) return; planSel.has(b.dataset.z) ? planSel.delete(b.dataset.z) : planSel.add(b.dataset.z); syncPlanChips(); };
  $('#planForm').onsubmit = (e) => { e.preventDefault(); buildCustom(); };
  $('#itinList').onclick = (e) => { const c = e.target.closest('[data-it]'); if (c) showItin(c.dataset.it); };
  if (S.plan) setTimeout(() => S.view === 'plan' && renderPlanResult(S.plan, false), 0);
}
function selectSeg(seg) {
  $$('.seg-btn').forEach((x) => { x.classList.toggle('active', x.dataset.seg === seg); x.setAttribute('aria-selected', x.dataset.seg === seg); });
  $$('.seg-pane').forEach((p) => p.classList.toggle('active', p.id === 'seg-' + seg));
}
function fillPlanStart() {
  const sel = $('#planStart'), prev = sel.value || 't:kalighat';
  const lines = ['blue', 'green', 'purple', 'orange', 'suburban'];
  const cap = (l) => l[0].toUpperCase() + l.slice(1);
  sel.innerHTML = `<option value="me">${t('f.me')}</option>`
    + lines.map((l) => `<optgroup label="${t('f.line', { line: cap(l) })}">${G.transit.filter((s) => s.line === l).map((s) => `<option value="t:${s.id}">${esc(s.name)}</option>`).join('')}</optgroup>`).join('')
    + `<optgroup label="${t('f.parkingGroup')}">${G.parking.map((p) => `<option value="p:${p.id}">🅿 ${esc(p.name)}</option>`).join('')}</optgroup>`;
  sel.value = prev;
}
function syncPlanChips() { $$('#planZones .chip').forEach((c) => c.setAttribute('aria-pressed', planSel.has(c.dataset.z))); }
function presetPlan(zones, startId) {
  planSel = new Set(zones); syncPlanChips();
  $('#planStart').value = 't:' + (startId || zoneOf(zones[0]).route.start);
  go('plan'); selectSeg('custom');
  buildCustom();
}
function openSharedPlan(p) {
  go('plan'); selectSeg('custom');
  if (!p) return;
  planSel = new Set(p.z.filter((z) => idx.zone[z])); syncPlanChips();
  const startOk = p.s === 'me' || (p.s.startsWith('t:') && idx.transit[p.s.slice(2)]) || (p.s.startsWith('p:') && idx.parking[p.s.slice(2)]);
  if (startOk) $('#planStart').value = p.s;
  if (/^\d\d:\d\d$/.test(p.t)) $('#planTime').value = p.t;
  if (p.r) $('#planStars').value = String(p.r);
  if (p.b) $('#planBudget').value = String(p.b);
  $('#planBrisk').checked = !!p.k;
  if (p.d && idx.day[p.d]) { S.day = p.d; $('#daySelect').value = p.d; }
  if (planSel.size) { buildCustom(); toast(t('share.loaded')); }
}

function renderItins() {
  $('#itinList').innerHTML = G.itineraries.map((it) => {
    const x = it.totals, d = idx.day[it.day];
    return `<li class="card" data-it="${it.id}" ${btn('')}>
      <div class="card-top"><h3>${esc((bn() && it.name_bn) || it.name)}</h3><span class="tag">${esc(dn(d))} · ${it.start_time}</span></div>
      <p>${esc((bn() && it.blurb_bn) || it.blurb)}</p>
      <div class="tags">${it.zones.map((z) => `<span class="tag"><span class="dot" style="display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;background:${zoneOf(z).color}"></span>${esc(zs(zoneOf(z)))}</span>`).join('')}</div>
      <div class="row"><span>${t('it.pandals', { n: it.pandal_count })}</span><span>🚶 ${x.walk_km} km</span><span>👣 ${fmt(stepsFor(x.walk_m ?? x.walk_km * 1000))}</span><span>🔥 ${fmt(kcalFor(x.walk_min, x.dwell_min))} kcal</span><span>${t('it.dur', { h: Math.floor(x.duration_min / 60), m: x.duration_min % 60 })}</span></div>
    </li>`;
  }).join('');
}

function showItin(id) {
  const it = G.itineraries.find((x) => x.id === id);
  const segs = it.segments.map((s) => s.type === 'ride'
    ? { type: 'ride', to: idx.transit[s.to_station], depart: s.depart, ride_min: s.ride_min }
    : { type: 'walk', zone: s.zone, start: idx.transit[s.start], stops: s.stops.map((x) => ({ ...x })) });
  const plan = {
    kind: 'trail', id: it.id, day: it.day, start: it.start_time, end: it.end_time, segments: segs,
    totals: { pandals: it.pandal_count, walk_m: it.totals.walk_m ?? it.totals.walk_km * 1000, walk_min: it.totals.walk_min, dwell_min: it.totals.dwell_min, ride_min: it.totals.ride_min, brisk: false },
  };
  S.plan = plan; store.set('activePlan', stripPlan(plan));
  renderPlanResult(plan);
}

function startPoint(val, cb) {
  if (val === 'me') {
    if (S.me) return cb({ id: 'me', lat: S.me[0], lng: S.me[1] });
    return locate((p) => cb({ id: 'me', lat: p[0], lng: p[1] }));
  }
  const [k, id] = val.split(':');
  const r = k === 't' ? idx.transit[id] : idx.parking[id];
  cb({ id: r.id, name: r.name, lat: r.lat, lng: r.lng });
}
const ptName = (pt) => (pt.id === 'me' ? t('plan.me') : pt.name);

function routeZone(start, pandals, clock, brisk) {
  const pts = pandals.map(ll), order = orderRoute(ll(start), pts);
  const speed = ((brisk ? M().walk_kmh_brisk : M().walk_kmh_crowd) * 1000) / 60;
  let cur = ll(start), walk = 0, wmin = 0, dwell = 0; const stops = [];
  for (const i of order) {
    const p = pandals[i], d = walkM(cur, pts[i]), w = Math.round(d / speed);
    clock += w;
    const c = crowdIndex(p.crowd_base, dayFactor(), Math.floor(clock / 60));
    const dw = Math.round(p.visit_min * (0.6 + (0.8 * c) / 100));
    stops.push({ pandal: p.id, walk_m: Math.round(d), walk_min: w, arrive: hhmm(clock), crowd: c, dwell_min: dw });
    clock += dw; walk += d; wmin += w; dwell += dw; cur = pts[i];
  }
  return { stops, walk, wmin, dwell, clock };
}
function entryStation(pandals) {
  let best, bd = Infinity;
  for (const s of G.transit) for (const p of pandals) { const d = hav(ll(s), ll(p)); if (d < bd) { bd = d; best = s; } }
  return best;
}
function planMulti(start, zones, minStars, startMin, brisk, exclude) {
  const groups = zones.map((z) => G.pandals.filter((p) => p.zone === z && p.popularity >= minStars && !exclude.has(p.id))).filter((g) => g.length);
  const ordered = []; let here = ll(start); const rest = [...groups];
  while (rest.length) { // visit the nearest zone next
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
    const last = idx.pandal[r.stops[r.stops.length - 1].pandal]; from = { id: last.id, name: last.name, lat: last.lat, lng: last.lng };
  });
  return { segments: segs, totals: { pandals: n, walk_m: walk, walk_min: wmin, dwell_min: dwell, ride_min: ride, brisk }, endMin: clock };
}

function buildCustom() {
  if (!planSel.size) return toast(t('plan.pickZone'));
  const zones = [...planSel], minStars = +$('#planStars').value, budget = +$('#planBudget').value, brisk = $('#planBrisk').checked;
  const timeVal = $('#planTime').value || '17:00';
  const [h, m] = timeVal.split(':').map(Number), startMin = h * 60 + m;
  const params = { z: zones, s: $('#planStart').value, t: timeVal, r: minStars, b: budget, k: brisk ? 1 : 0, d: S.day };
  startPoint(params.s, (start) => {
    const exclude = new Set();
    let res = planMulti(start, zones, minStars, startMin, brisk, exclude);
    const total = (r) => r.totals.walk_min + r.totals.dwell_min + r.totals.ride_min;
    // Over budget? Drop the stop that costs the most minutes (detour + dwell) per unit of fame, then re-plan.
    const speed = ((brisk ? M().walk_kmh_brisk : M().walk_kmh_crowd) * 1000) / 60;
    while (total(res) > budget && res.totals.pandals > 1) {
      const all = res.segments.filter((s) => s.type === 'walk').flatMap((s) => s.stops);
      const pts = [ll(start), ...all.map((x) => ll(idx.pandal[x.pandal]))];
      let worst = null, worstScore = -Infinity;
      all.forEach((x, i) => {
        const prev = pts[i], cur = pts[i + 1], next = pts[i + 2];
        const detour = walkM(prev, cur) + (next ? walkM(cur, next) - walkM(prev, next) : 0);
        const score = (detour / speed + x.dwell_min) / idx.pandal[x.pandal].popularity ** 2;
        if (score > worstScore) { worstScore = score; worst = x.pandal; }
      });
      exclude.add(worst);
      res = planMulti(start, zones, minStars, startMin, brisk, exclude);
    }
    if (!res.totals.pandals) return toast(t('plan.none'));
    const plan = { kind: 'custom', zones, day: S.day, start: hhmm(startMin), end: hhmm(res.endMin), startPt: start,
      segments: res.segments, totals: res.totals, skipped: exclude.size, params };
    S.plan = plan; store.set('activePlan', stripPlan(plan));
    renderPlanResult(plan);
  });
}
// Plans are stored by ID only; names are resolved at render time so the language toggle works.
const stripPlan = (plan) => JSON.parse(JSON.stringify(plan, (k, v) => (k === 'p' ? undefined : v)));
const stopsOf = (plan) => plan.segments.filter((s) => s.type === 'walk').flatMap((s) => s.stops);
const planTitle = (plan) => {
  if (plan.kind === 'trail') { const it = G.itineraries.find((i) => i.id === plan.id); return (bn() && it.name_bn) || it.name; }
  return (plan.zones || []).map((z) => zs(zoneOf(z))).join(' + ');
};
const planShareUrl = (plan) => location.origin + location.pathname + (plan.kind === 'trail' ? '#trail=' + plan.id : '#plan=' + encodePlan(plan.params));

async function sharePlan(plan) {
  const url = planShareUrl(plan), text = t('share.text', { title: planTitle(plan) });
  try {
    if (navigator.share) { await navigator.share({ title: 'Pujo Parikrama', text, url }); return; }
    await navigator.clipboard.writeText(`${text}\n${url}`); toast(t('share.copied'));
  } catch (e) {
    if (e?.name !== 'AbortError') prompt('Copy this link', url);
  }
}

function renderPlanResult(plan, scroll = true) {
  if (!plan.kind || !plan.segments || !stopsOf(plan).every((x) => idx.pandal[x.pandal])) return; // stale saved plan from an older dataset
  const box = $('#planResult'); box.hidden = false;
  const x = plan.totals, steps = stepsFor(x.walk_m), kcal = kcalFor(x.walk_min, x.dwell_min, x.brisk);
  const walkSegs = plan.segments.filter((s) => s.type === 'walk');
  const stopsAll = stopsOf(plan);
  const firstStart = plan.startPt || walkSegs[0].start;
  const pts = [ll(firstStart), ...stopsAll.map((s) => ll(idx.pandal[s.pandal]))];
  const legs = routeUrls(pts);
  const sub = t('plan.sub', { day: dn(idx.day[plan.day]), from: plan.start, to: plan.end, start: esc(ptName(firstStart)) });

  let n = 0, lastFood = -9; const usedFood = new Set();
  const tl = [`<li class="start"><div class="t">${plan.start}</div><div class="nm">${t('tl.start', { name: esc(ptName(firstStart)) })}</div></li>`];
  for (const s of plan.segments) {
    if (s.type === 'ride') { tl.push(`<li class="ride"><div class="t">${s.depart}</div><div class="nm">${t('tl.ride', { name: esc(s.to.name) })}</div><div class="sub">${t('tl.rideMin', { n: s.ride_min })}</div></li>`); continue; }
    for (const st of s.stops) {
      n++;
      const p = idx.pandal[st.pandal];
      const hour = +st.arrive.slice(0, 2), meal = (hour >= 12 && hour <= 14) || (hour >= 19 && hour <= 21);
      let eat = '';
      const f = p.food.filter((ff) => ff.distance_m <= 800).map((ff) => idx.food[ff.id]).find((ff) => !usedFood.has(ff.id));
      if (f && (n - lastFood >= 3 || (meal && n - lastFood >= 2))) { usedFood.add(f.id); lastFood = n; eat = `<div class="eat">${t('tl.eat', { dish: esc(f.dishes[0]), place: esc(f.name) })}</div>`; }
      const v = S.checkins[st.pandal] ? ' ✓' : '';
      tl.push(`<li data-n="${n}" data-p="${st.pandal}" ${btn('')}><div class="t">${st.arrive}</div><div class="nm">${esc(nm(p))}${v}</div>
        <div class="sub">${st.walk_m ? `${t('tl.walk', { m: st.walk_m })} · ` : ''}${crowdWord(st.crowd)} · ${t('tl.inside', { n: st.dwell_min })}</div>${eat}</li>`);
    }
  }
  box.innerHTML = `
    <div class="plan-sum">
      <h3>${esc(planTitle(plan))}</h3><div class="fine">${sub}${plan.skipped ? ` · ${t('plan.dropped', { n: plan.skipped })}` : ''}</div>
      <div class="kpis"><div><b>${x.pandals}</b><span>${t('kpi.pandals')}</span></div><div><b>${km(x.walk_m)}</b><span>${t('kpi.km')}</span></div><div><b>${fmt(steps)}</b><span>${t('kpi.steps')}</span></div><div><b>${fmt(kcal)}</b><span>${t('kpi.kcal')}</span></div></div>
      <div class="btn-row">
        <button class="btn primary" id="planWalk">${t('plan.startWalk')}</button>
        <button class="btn" id="planShare">↗ ${t('plan.share')}</button>
      </div>
      <div class="btn-row" style="margin-top:8px">${legs.map((u, i) => `<a class="btn sm" target="_blank" rel="noopener" href="${u}">${t('plan.maps')}${legs.length > 1 ? ` · ${t('plan.leg', { n: i + 1 })}` : ''}</a>`).join('')}</div>
    </div>
    <div id="planMap" class="map short" style="margin:12px 16px;border-radius:16px;overflow:hidden"></div>
    <ol class="timeline">${tl.join('')}</ol>`;
  $('#planWalk').onclick = () => { S.plan = plan; store.set('activePlan', stripPlan(plan)); go('fit'); if (!S.walk) startWalk(); };
  $('#planShare').onclick = () => sharePlan(plan);
  $('.timeline').onclick = (e) => { const li = e.target.closest('[data-p]'); if (li) pandalSheet(li.dataset.p); };

  if (planMap) { planMap.remove(); planMap = null; }
  planMap = makeMap($('#planMap'));
  if (planMap) {
    L.polyline(pts, { color: '#9F1239', weight: 4, opacity: .85, dashArray: '2 8', lineCap: 'round' }).addTo(planMap);
    L.marker(pts[0], { icon: L.divIcon({ className: '', html: '<div class="seq" style="background:#1C1917">▶</div>', iconSize: [26, 26] }), keyboard: false }).addTo(planMap);
    stopsAll.forEach((st, i) => L.marker(ll(idx.pandal[st.pandal]), { icon: L.divIcon({ className: '', html: `<div class="seq">${i + 1}</div>`, iconSize: [26, 26] }), title: nm(idx.pandal[st.pandal]) })
      .on('click', () => pandalSheet(st.pandal)).addTo(planMap));
    planMap.fitBounds(L.latLngBounds(pts), { padding: [24, 24] });
  }
  if (scroll) window.scrollTo({ top: box.getBoundingClientRect().top + window.scrollY - $('.topbar').offsetHeight - 8, behavior: 'smooth' });
}

/* ---------------- FOOD ---------------- */
function zoneChipsHtml(sel) {
  return [`<button class="chip" data-z="all" aria-pressed="${sel === 'all'}">${t('zones.all')}</button>`,
    ...G.zones.map((z) => `<button class="chip" data-z="${z.id}" aria-pressed="${sel === z.id}"><span class="dot" style="background:${z.color}"></span>${esc(zs(z))}</button>`)].join('');
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
    const z = zoneOf(f.zone), near = f.near_pandals.slice(0, 3).map((id) => nm(idx.pandal[id]));
    const vegDot = f.veg === 'veg' ? '🟢' : f.veg === 'nonveg' ? '🔴' : '🟢🔴';
    return `<li class="card" data-food="${f.id}" ${btn(`aria-label="${esc(f.name)}"`)}>
      <div class="card-top"><div><h3>${esc(f.name)}</h3><div class="zl"><span class="dot" style="background:${z.color}"></span>${esc(zs(z))} · ${t('type.' + f.type)} · ${'₹'.repeat(f.price)}</div></div><span title="${t('diet.' + f.veg)}">${vegDot}</span></div>
      <div class="tags">${f.dishes.map((d) => `<span class="tag">${esc(d)}</span>`).join('')}</div>
      <p>${esc(f.note)}</p>
      <div class="row"><span>${isOpen(f.hours) ? t('food.open') : t('food.closed')} · ${esc(f.hours)}</span>${near.length ? `<span>${t('food.near', { list: esc(near.join(', ')) })}</span>` : ''}</div>
    </li>`;
  }).join('') || `<li class="empty">${t('food.none')}</li>`;
}
function foodSheet(id) {
  const f = idx.food[id];
  openSheet(`<h2>${esc(f.name)}</h2><p class="lead">${esc(f.note)}</p>
    <div class="tags">${f.dishes.map((d) => `<span class="tag">${esc(d)}</span>`).join('')}</div>
    <dl class="kv"><dt>${t('food.hours')}</dt><dd>${esc(f.hours)} ${t('food.hoursNote')}</dd><dt>${t('food.budget')}</dt><dd>${'₹'.repeat(f.price)}</dd><dt>${t('food.diet')}</dt><dd>${t('diet.' + f.veg)}</dd></dl>
    <h2 class="h2">${t('food.walkable')}</h2>
    <ul class="mini-list">${f.near_pandals.map((pid) => `<li data-p="${pid}" ${btn('')}><b>${esc(nm(idx.pandal[pid]))}</b><small>${km(hav(ll(f), ll(idx.pandal[pid])))} km</small></li>`).join('') || `<li>${t('food.noneNear')}</li>`}</ul>
    <div class="btn-row"><a class="btn primary" target="_blank" rel="noopener" href="${dirUrl(ll(f))}">${t('p.directions')}</a><button class="btn" id="ateBtn">${t('food.ate')}</button></div>`,
  (el) => {
    el.querySelectorAll('[data-p]').forEach((li) => (li.onclick = () => pandalSheet(li.dataset.p)));
    $('#ateBtn', el).onclick = () => { logFood(f.id); toast(t('food.logged', { name: f.name })); };
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
    ? `<div class="zbox" style="--zc:#1D4ED8"><h3>${t('car.yours')}</h3><p>${t('car.saved', { when: new Date(car.ts).toLocaleString(bn() ? 'bn-IN' : 'en-IN', { weekday: 'short', hour: 'numeric', minute: '2-digit' }) })}${S.me ? ` · ${t('car.fromYou', { km: km(hav(S.me, [car.lat, car.lng])) })}` : ''}</p>
       <div class="btn-row" style="margin-top:8px"><a class="btn sm primary" target="_blank" rel="noopener" href="${dirUrl([car.lat, car.lng])}">${t('car.walkBack')}</a><button class="btn sm" id="carClear">${t('car.clear')}</button></div></div>`
    : `<button class="btn block" id="carSave">${t('car.save')}</button>`;
  if (car) $('#carClear').onclick = () => { S.car = null; store.set('car', null); renderPark(); };
  else $('#carSave').onclick = () => locate((p) => { S.car = { lat: p[0], lng: p[1], ts: Date.now() }; store.set('car', S.car); toast(t('car.savedToast')); renderPark(); });

  $('#parkZones').innerHTML = zoneChipsHtml(S.parkZone);
  const zl = S.parkZone === 'all' ? G.zones : [zoneOf(S.parkZone)];
  $('#parkAdvisory').innerHTML = zl.map((z) => `<div class="adv ${z.car_advisory}" style="margin-top:8px"><b>${esc(zs(z))}: ${t('adv.' + z.car_advisory)}</b><span>${esc(z.walk_tip)}</span></div>`).join('');
  const plist = G.parking.filter((p) => S.parkZone === 'all' || p.zone === S.parkZone);
  $('#parkList').innerHTML = plist.map((p) => `<li class="card" data-park="${p.id}" ${btn(`aria-label="${esc(p.name)}"`)}>
    <div class="card-top"><div><h3>🅿 ${esc(p.name)}</h3><div class="zl">${t('kind.' + p.kind)} · ${esc(p.capacity)} · ${esc(p.rate_hint)}</div></div></div>
    <p>${esc(p.note)}</p></li>`).join('') || `<li class="empty">${t('park.none')}</li>`;
  const near = S.parkZone === 'all' ? G.transit : G.transit.filter((s) => zoneOf(S.parkZone).pandal_ids.some((id) => hav(ll(s), ll(idx.pandal[id])) < 2500));
  $('#transitList').innerHTML = near.map((s) => `<li class="card"><div class="card-top"><b><span class="line-${s.line}">●</span> ${esc(s.name)}</b><small class="fine">${s.line}</small></div></li>`).join('');
}
function parkSheet(id) {
  const p = idx.parking[id];
  const pandals = G.pandals.map((x) => [x, hav(ll(p), ll(x))]).filter(([, d]) => d < 2000).sort((a, b) => a[1] - b[1]).slice(0, 5);
  openSheet(`<h2>🅿 ${esc(p.name)}</h2><p class="lead">${esc(p.note)}</p>
    <dl class="kv"><dt>${t('park.type')}</dt><dd>${t('kind.' + p.kind)}</dd><dt>${t('park.size')}</dt><dd>${esc(p.capacity)}</dd><dt>${t('park.rate')}</dt><dd>${esc(p.rate_hint)} ${t('park.approx')}</dd></dl>
    <h2 class="h2">${t('park.walkTo')}</h2>
    <ul class="mini-list">${pandals.map(([x, d]) => `<li data-p="${x.id}" ${btn('')}><b>${esc(nm(x))}</b><small>${km(d * M().detour)} km</small></li>`).join('') || `<li>${t('park.onward')}</li>`}</ul>
    <div class="btn-row"><a class="btn primary" target="_blank" rel="noopener" href="${dirUrl(ll(p), 'driving')}">${t('park.drive')}</a></div>`,
  (el) => el.querySelectorAll('[data-p]').forEach((li) => (li.onclick = () => pandalSheet(li.dataset.p))));
}

/* ---------------- FIT ---------------- */
const BADGES = [
  { id: 'first', em: '🪔', name: 'Prothom Darshan', bn: 'প্রথম দর্শন' },
  { id: 'five', em: '🖐️', name: 'Panch Pandal', bn: 'পাঁচ প্যান্ডেল' },
  { id: 'fifteen', em: '🥁', name: 'Dhaki', bn: 'ঢাকি' },
  { id: 'thirty', em: '👑', name: 'Pujo Legend', bn: 'পুজো কিংবদন্তি' },
  { id: 'zone', em: '🗺️', name: 'Zone Master', bn: 'অঞ্চল-জয়ী' },
  { id: 'k10', em: '🏃', name: '10K Pujo', bn: '১০ কিমি পুজো' },
  { id: 'ashtami', em: '🔥', name: 'Ashtami Marathon', bn: 'অষ্টমী ম্যারাথন' },
  { id: 'dawn', em: '🌅', name: 'Bhor-er Pakhi', bn: 'ভোরের পাখি' },
  { id: 'owl', em: '🦉', name: 'Raat Jaga', bn: 'রাত জাগা' },
  { id: 'foodie', em: '😋', name: 'Pet Pujo', bn: 'পেটপুজো' },
  { id: 'ns', em: '🧭', name: 'Uttor–Dokkhin', bn: 'উত্তর–দক্ষিণ' },
  { id: 'goal', em: '🎯', name: 'Goal Getter', bn: 'লক্ষ্যভেদ' },
];
const badgeName = (b) => (bn() ? b.bn : b.name);
/* Steps for a day: sensor and GPS-estimated steps accumulate in rec.steps. Older records fall back to distance. */
const daySteps = (r) => (r.steps != null ? Math.round(r.steps) : stepsFor(r.m || 0));
const dayDist = (r) => Math.max(r.m || 0, r.steps != null && !r.m ? r.steps * stride() : 0);
const dayWalkMin = (r) => Math.max((r.ms || 0) / 60000, (daySteps(r) * stride()) / ((M().walk_kmh_crowd * 1000) / 60));

function earned() {
  const ids = Object.keys(S.checkins), n = ids.length, got = new Set();
  if (n >= 1) got.add('first'); if (n >= 5) got.add('five'); if (n >= 15) got.add('fifteen'); if (n >= 30) got.add('thirty');
  if (G.zones.some((z) => z.pandal_ids.every((id) => S.checkins[id]))) got.add('zone');
  const hours = Object.values(S.checkins).map((c) => new Date(c.ts).getHours());
  if (hours.some((h) => h >= 4 && h < 7)) got.add('dawn');
  if (hours.some((h) => h >= 0 && h < 4)) got.add('owl');
  if (new Set(Object.values(S.history).flatMap((d) => d.foods || [])).size >= 3) got.add('foodie');
  for (const [date, d] of Object.entries(S.history)) {
    if (dayDist(d) >= 10000) got.add('k10');
    if (date === idx.day.ashtami.date && daySteps(d) >= 20000) got.add('ashtami');
    if (daySteps(d) >= S.prefs.goal) got.add('goal');
    const zset = new Set((d.pandals || []).map((id) => idx.pandal[id]?.zone));
    if (zset.has('north') && (zset.has('south_gariahat') || zset.has('south_lakemarket') || zset.has('southwest'))) got.add('ns');
  }
  return got;
}
function dayRec(key = todayKey()) {
  const r = (S.history[key] ||= { m: 0, ms: 0, pandals: [], foods: [] });
  if (r.steps == null) r.steps = stepsFor(r.m || 0);
  return r;
}
function saveHistory() { store.set('history', S.history); }
function checkin(id, how) {
  if (S.checkins[id]) return false;
  const before = earned();
  S.checkins[id] = { ts: Date.now(), how }; store.set('checkins', S.checkins);
  const d = dayRec(); if (!d.pandals.includes(id)) d.pandals.push(id); saveHistory();
  toast(t('checkin.toast', { name: nm(idx.pandal[id]) }));
  if (navigator.vibrate) navigator.vibrate(60);
  announceBadges(before);
  return true;
}
function logFood(id) { const before = earned(); const d = dayRec(); if (!d.foods.includes(id)) d.foods.push(id); saveHistory(); announceBadges(before); }
function announceBadges(before) {
  const now = earned();
  for (const b of BADGES) if (now.has(b.id) && !before.has(b.id)) setTimeout(() => toast(t('badge.toast', { em: b.em, name: badgeName(b) })), 1400);
}

function setupFit() {
  $('#walkBtn').onclick = () => (S.walk ? stopWalk() : startWalk());
  $('#pHeight').value = S.prefs.height; $('#pWeight').value = S.prefs.weight; $('#pGoal').value = S.prefs.goal;
  $('#pLowData').checked = S.prefs.lowData; $('#pMotion').checked = S.prefs.motion;
  $('#profileForm').onsubmit = (e) => {
    e.preventDefault();
    const lowBefore = S.prefs.lowData;
    S.prefs = { ...S.prefs, height: +$('#pHeight').value || 165, weight: +$('#pWeight').value || 65, goal: +$('#pGoal').value || 10000,
      lowData: $('#pLowData').checked, motion: $('#pMotion').checked };
    store.set('prefs', S.prefs); toast(t('fit.savedToast')); renderFit();
    if (lowBefore !== S.prefs.lowData) location.reload();
  };
  $('#resetBtn').onclick = () => { if (confirm(t('fit.confirmReset'))) { store.clear(); location.reload(); } };
}

async function startWalk() {
  if (!navigator.geolocation) return toast(t('fit.noGps'));
  // iOS only grants motion access from inside a user gesture, so ask before anything else is awaited.
  if (S.prefs.motion && window.DeviceMotionEvent) {
    try {
      if (typeof DeviceMotionEvent.requestPermission === 'function') {
        if ((await DeviceMotionEvent.requestPermission()) === 'granted') attachMotion();
      } else attachMotion();
    } catch { /* fall back to GPS steps */ }
  }
  S.walk = { last: null, startedAt: Date.now() };
  store.set('walking', true);
  S.watchId = navigator.geolocation.watchPosition(onPos, (err) => {
    $('#walkStatus').textContent = err.code === 1 ? t('fit.denied') : t('fit.waiting');
  }, { enableHighAccuracy: true, maximumAge: 3000, timeout: 30000 });
  try { S.wakeLock = await navigator.wakeLock?.request('screen'); } catch { /* not supported */ }
  renderFit();
}
function stopWalk() {
  if (S.watchId != null) navigator.geolocation.clearWatch(S.watchId);
  removeEventListener('devicemotion', onMotion);
  S.watchId = null; S.walk = null; S.detector = null; store.set('walking', false);
  try { S.wakeLock?.release(); } catch { /* ignore */ } S.wakeLock = null;
  saveHistory(); toast(t('fit.saved')); renderFit();
}
document.addEventListener('visibilitychange', async () => {
  if (document.visibilityState === 'visible' && S.walk && !S.wakeLock) { try { S.wakeLock = await navigator.wakeLock?.request('screen'); } catch { /* ignore */ } }
  if (document.visibilityState === 'hidden') saveHistory();
});

function attachMotion() { S.detector = new StepDetector(); addEventListener('devicemotion', onMotion); }
const motionLive = () => Date.now() - S.lastMotion < 3000;
let motionSaveT = 0, motionRenderT = 0;
function onMotion(e) {
  const a = e.accelerationIncludingGravity;
  if (!S.walk || !S.detector || !a || a.x == null) return;
  S.lastMotion = Date.now();
  const added = S.detector.push(a.x, a.y, a.z, e.timeStamp || performance.now());
  if (!added) return;
  dayRec().steps += added;
  const now = Date.now();
  if (now - motionSaveT > 10000) { motionSaveT = now; saveHistory(); }
  if (now - motionRenderT > 1000) { motionRenderT = now; if (S.view === 'fit') renderFit(); }
}

/* GPS fixes: noisy ones and vehicle-speed ones are discarded (see core.judgeFix). */
function onPos(pos) {
  const { latitude: lat, longitude: lng, accuracy } = pos.coords;
  S.me = [lat, lng]; drawMe();
  const w = S.walk; if (!w) return;
  const fix = { lat, lng, accuracy, t: pos.timestamp || Date.now() };
  const v = judgeFix(w.last, fix);
  if (v.reason === 'inaccurate') { $('#walkStatus').textContent = t('fit.weak', { m: Math.round(accuracy) }); return; }
  if (v.use) {
    const rec = dayRec(); rec.m += v.dist; rec.ms += v.dt * 1000;
    if (!motionLive()) rec.steps += v.dist / stride(); // without a live motion sensor, estimate steps from distance
    saveHistory();
  }
  if (v.keep) w.last = fix;
  for (const pd of G.pandals) if (!S.checkins[pd.id] && hav([lat, lng], ll(pd)) <= M().checkin_radius_m) checkin(pd.id, 'gps');
  for (const f of G.food) if (hav([lat, lng], ll(f)) <= 30) logFood(f.id);
  renderFit();
}

function nextStopText() {
  if (!S.plan || !S.plan.segments) return '';
  const stops = stopsOf(S.plan).filter((x) => idx.pandal[x.pandal]);
  if (!stops.length) return '';
  const next = stops.find((x) => !S.checkins[x.pandal]);
  if (!next) return t('fit.planDone');
  const p = idx.pandal[next.pandal];
  const done = stops.filter((x) => S.checkins[x.pandal]).length;
  const dist = S.me ? ` · ${km(walkM(S.me, ll(p)))} km` : '';
  return `${t('fit.next', { d: done, n: stops.length, name: `<b>${esc(nm(p))}</b>` })}${dist} <a href="${dirUrl(ll(p))}" target="_blank" rel="noopener">${t('p.directions')}</a>`;
}

function renderFit() {
  const d = S.history[todayKey()] || { m: 0, ms: 0, pandals: [] };
  const steps = daySteps(d), goal = S.prefs.goal, mins = dayWalkMin(d);
  $('#fitSteps').textContent = fmt(steps); $('#fitGoal').textContent = t('fit.of', { n: fmt(goal) });
  $('#fitKm').textContent = km(dayDist(d)); $('#fitKcal').textContent = fmt(kcalFor(mins));
  $('#fitTime').textContent = `${Math.floor(mins / 60)}:${String(Math.floor(mins % 60)).padStart(2, '0')}`;
  $('#fitPandals').textContent = d.pandals.length;
  const C = 2 * Math.PI * 86; $('#ringFg').style.strokeDashoffset = C * (1 - Math.min(1, steps / goal));
  $('#fitSource').textContent = S.walk ? (motionLive() ? t('fit.src.motion') : t('fit.src.gps')) : '';

  const b = $('#walkBtn');
  if (S.walk) { b.classList.add('live'); b.innerHTML = `<span class="pulse"></span> ${t('fit.tracking')}`; }
  else { b.classList.remove('live'); b.textContent = store.get('walking', false) ? t('fit.resume') : t('fit.start'); }
  const nxt = nextStopText();
  $('#walkStatus').innerHTML = nxt || (S.walk ? t('fit.live') : t('fit.idle'));

  const got = earned();
  $('#badgeList').innerHTML = BADGES.map((x) => `<li class="badge ${got.has(x.id) ? 'got' : ''}"><span class="em" aria-hidden="true">${x.em}</span>${esc(badgeName(x))}<br><small class="fine">${t('b.' + x.id)}</small></li>`).join('');

  const rows = Object.entries(S.history).sort((a, c) => c[0].localeCompare(a[0]));
  const dayName = (date) => { const pd = G.meta.days.find((x) => x.date === date); return pd ? dn(pd) : null; };
  $('#historyList').innerHTML = rows.map(([date, r]) => `<li><span><b>${dayName(date) || new Date(date + 'T00:00').toLocaleDateString(bn() ? 'bn-IN' : 'en-IN', { day: 'numeric', month: 'short' })}</b> · ${t('fit.dayRow', { n: (r.pandals || []).length })}</span><span>${t('fit.dayStats', { s: fmt(daySteps(r)), km: km(dayDist(r)) })}</span></li>`).join('')
    || `<li><span class="fine">${t('fit.noDays')}</span></li>`;
}

boot();
