/* Explore: one map with Pandals / Food / Parking segments, zone filter and lists. */
import { hav, isOpen } from '../core.js';
import {
  S, G, idx, t, store, community, ll, nm, zn, zs, zoneOf, esc, dist, ampm, dn, crowdNow, btn, icon,
} from '../state.js';
import { $, registerView, makeMap, pinIcon, getFix, toast } from '../ui.js';
import { openPlace, crowdPill, statsHtml, dirUrl } from '../sheets.js';
import { visitedToday } from '../actions.js';

let map = null, layers = {}, meMarker = null;
const LINE = { blue: '#2563EB', green: '#16A34A', purple: '#9333EA', orange: '#EA580C', suburban: '#57534E' };

export function setExplore(patch) { Object.assign(S.explore, patch); }

function ensureMap() {
  if (map || !$('#map')) return;
  map = makeMap($('#map'));
  if (!map) return;
  layers = { pandals: L.layerGroup(), food: L.layerGroup(), parking: L.layerGroup(), transit: L.layerGroup() };
  for (const p of G.data.pandals) L.marker(ll(p), { icon: pinIcon(zoneOf(p.zone).color, 14 + p.popularity * 3, p.popularity === 5 ? '★' : ''), title: p.name }).on('click', () => openPlace(p.id)).addTo(layers.pandals);
  for (const f of G.data.food) L.marker(ll(f), { icon: pinIcon('#C2410C', 22, '🍴'), title: f.name }).on('click', () => openPlace(f.id)).addTo(layers.food);
  for (const p of G.data.parking) L.marker(ll(p), { icon: pinIcon('#1D4ED8', 22, 'P', 'sq'), title: p.name }).on('click', () => openPlace(p.id)).addTo(layers.parking);
  for (const s of G.data.transit) L.marker(ll(s), { icon: pinIcon(LINE[s.line], 18, 'M', 'sq'), title: s.name, keyboard: false }).bindTooltip(s.name).addTo(layers.transit);
  layers.transit.addTo(map);
  $('#locateBtn').onclick = () => getFix().then((f) => { drawMe(); map.setView([f.lat, f.lng], 15); render(); }).catch(() => toast(t('loc.fail')));
}
export function drawMe() {
  if (!map || !S.me) return;
  if (!meMarker) meMarker = L.marker(S.me, { icon: L.divIcon({ className: '', html: '<div class="me-dot"></div>', iconSize: [16, 16] }), zIndexOffset: 1000, keyboard: false }).addTo(map);
  else meMarker.setLatLng(S.me);
}
function syncLayers() {
  if (!map) return;
  const seg = S.explore.seg;
  layers.pandals.addTo(map);
  seg === 'food' ? layers.food.addTo(map) : layers.food.remove();
  seg === 'parking' ? layers.parking.addTo(map) : layers.parking.remove();
}
let lastFit = '';
function fitZone() {
  if (!map) return;
  const key = S.explore.zone;
  if (key === lastFit) return; lastFit = key;
  if (key === 'all') map.setView([22.555, 88.37], 12);
  else map.fitBounds(zoneOf(key).bbox, { padding: [30, 30], maxZoom: 16 });
}

const zoneChips = (sel) => [`<button class="chip" data-z="all" aria-pressed="${sel === 'all'}">${t('zones.all')}</button>`,
  ...G.data.zones.map((z) => `<button class="chip" data-z="${z.id}" aria-pressed="${sel === z.id}"><span class="dot" style="background:${z.color}"></span>${esc(zs(z))}</button>`)].join('');

function pandalItem(p) {
  const z = zoneOf(p.zone), c = crowdNow(p);
  return `<li class="item ${visitedToday(p.id) ? 'visited' : ''}" data-place="${p.id}" style="--zc:${z.color}" ${btn(`aria-label="${esc(nm(p))}"`)}>
    <h3 class="nm">${esc(nm(p))}</h3>
    <div class="side"><span class="score">${icon('star', 'sm fill')}${p.popularity}</span>${statsHtml(p.id, { compact: true })}</div>
    <div class="meta">${esc(zs(z))}${S.me ? ` · ${dist(hav(S.me, ll(p)))}` : ''} · 🚇 ${esc(p.nearest_metro.name)}</div>
    <div class="status">${crowdPill(c)}<span class="pill">${icon('clock', 'sm')} ${t('card.best', { slot: t('slot.' + p.best_slot) })}</span></div>
  </li>`;
}
function foodItem(f) {
  const z = zoneOf(f.zone), open = isOpen(f.hours);
  const near = f.near_pandals.slice(0, 2).map((id) => nm(idx.pandal[id]));
  return `<li class="item ${visitedToday(f.id) ? 'visited' : ''}" data-place="${f.id}" style="--zc:${z.color}" ${btn(`aria-label="${esc(f.name)}"`)}>
    <h3 class="nm">${esc(f.name)}</h3>
    <div class="side"><span class="score">${'₹'.repeat(f.price)}</span>${statsHtml(f.id, { compact: true })}</div>
    <div class="meta">${esc(f.dishes.slice(0, 3).join(' · '))}</div>
    <div class="status"><span class="pill ${open ? 'ok' : ''}">${open ? t('food.open') : t('food.closed')}</span><span class="pill">${f.veg === 'veg' ? '🟢' : f.veg === 'nonveg' ? '🔴' : '🟢🔴'} ${t('diet.' + f.veg)}</span>${near.length ? `<span class="fine">${t('food.near', { list: esc(near.join(', ')) })}</span>` : ''}</div>
  </li>`;
}

function render() {
  ensureMap(); syncLayers(); fitZone(); drawMe();
  const e = S.explore, panel = $('#explorePanel');
  const segs = [['pandals', 'star', t('seg.pandals')], ['food', 'food', t('seg.food')], ['parking', 'car', t('seg.parking')]];
  let body = '';
  if (e.seg === 'pandals') {
    const list = G.data.pandals.filter((p) => e.zone === 'all' || p.zone === e.zone);
    if (e.sort === 'popular') list.sort((a, b) => b.popularity - a.popularity || crowdNow(a) - crowdNow(b));
    if (e.sort === 'quiet') list.sort((a, b) => crowdNow(a) - crowdNow(b) || b.popularity - a.popularity);
    if (e.sort === 'near' && S.me) list.sort((a, b) => hav(S.me, ll(a)) - hav(S.me, ll(b)));
    if (e.sort === 'live') list.sort((a, b) => (community.statFor(b.id)?.last_hour || 0) - (community.statFor(a.id)?.last_hour || 0) || b.popularity - a.popularity);
    const z = e.zone !== 'all' ? zoneOf(e.zone) : null;
    body = `${z ? `<div class="notice ${z.car_advisory}"><b>${esc(zn(z))}</b><span>${esc(z.vibe)}</span><span>${t('car.' + z.car_advisory)} · ${esc(z.walk_tip)}</span></div>` : ''}
      <div class="time-row"><label for="hourRange">${t('crowd.at')}</label><input type="range" id="hourRange" min="0" max="23" value="${S.hour}"><strong>${ampm(S.hour)}, ${esc(dn(idx.day[S.day]))}</strong></div>
      <div class="toolbar"><span>${t('list.count', { n: list.length })}</span>
        <select id="sortSelect" aria-label="${t('sort.label')}">
          ${['popular', 'quiet', 'near', ...(community.enabled ? ['live'] : [])].map((k) => `<option value="${k}" ${e.sort === k ? 'selected' : ''}>${t('sort.' + k)}</option>`).join('')}
        </select></div>
      <ul class="list">${list.map(pandalItem).join('')}</ul>`;
  } else if (e.seg === 'food') {
    const F = e.food;
    const list = G.data.food.filter((f) => (e.zone === 'all' || f.zone === e.zone)
      && (!F.has('veg') || f.veg === 'veg') && (!F.has('cheap') || f.price === 1)
      && (!F.has('sweets') || f.type === 'sweets' || f.type === 'drinks') && (!F.has('street') || f.type === 'street')
      && (!F.has('open') || isOpen(f.hours)));
    if (S.me) list.sort((a, b) => hav(S.me, ll(a)) - hav(S.me, ll(b)));
    body = `<div class="chips" id="foodFilters">${['veg', 'cheap', 'sweets', 'street', 'open'].map((k) => `<button class="chip" data-f="${k}" aria-pressed="${F.has(k)}">${t('ff.' + k)}</button>`).join('')}</div>
      <ul class="list">${list.map(foodItem).join('') || `<li class="empty">${t('food.none')}</li>`}</ul>`;
  } else {
    const car = S.car;
    const zl = e.zone === 'all' ? G.data.zones : [zoneOf(e.zone)];
    const plist = G.data.parking.filter((p) => e.zone === 'all' || p.zone === e.zone);
    const near = e.zone === 'all' ? G.data.transit : G.data.transit.filter((s) => zoneOf(e.zone).pandal_ids.some((id) => hav(ll(s), ll(idx.pandal[id])) < 2500));
    body = `<div class="pad" style="margin-bottom:10px">${car
      ? `<div class="card"><b>${t('car.yours')}</b><p class="fine" style="margin:2px 0 8px">${t('car.saved', { when: new Date(car.ts).toLocaleString(S.prefs.lang === 'bn' ? 'bn-IN' : 'en-IN', { weekday: 'short', hour: 'numeric', minute: '2-digit' }) })}${S.me ? ` · ${dist(hav(S.me, [car.lat, car.lng]))}` : ''}</p>
         <div class="btn-row"><a class="btn sm primary" target="_blank" rel="noopener" href="${dirUrl([car.lat, car.lng])}">${t('car.walkBack')}</a><button class="btn sm" id="carClear">${t('car.clear')}</button></div></div>`
      : `<button class="btn block" id="carSave">${icon('pin')} ${t('car.save')}</button>`}</div>
      ${zl.map((z) => `<div class="notice ${z.car_advisory}"><b>${esc(zs(z))}: ${t('adv.' + z.car_advisory)}</b><span>${esc(z.walk_tip)}</span></div>`).join('')}
      <div class="section-head" style="margin-top:16px"><h2>${t('h.parking')}</h2></div>
      <ul class="list">${plist.map((p) => `<li class="item" data-place="${p.id}" style="--zc:#1D4ED8" ${btn(`aria-label="${esc(p.name)}"`)}>
        <h3 class="nm">${esc(p.name)}</h3><div class="side"><span class="count">${esc(p.rate_hint)}</span></div>
        <div class="meta">${t('kind.' + p.kind)} · ${esc(p.capacity)}</div><div class="status"><span class="fine">${esc(p.note)}</span></div></li>`).join('') || `<li class="empty">${t('park.none')}</li>`}</ul>
      <div class="section-head" style="margin-top:16px"><h2>${t('h.transit')}</h2></div>
      <div class="chips wrap pad">${near.map((s) => `<span class="pill"><span class="line-${s.line}">●</span> ${esc(s.name)}</span>`).join('')}</div>
      <p class="fine pad" style="margin-top:12px">${t('park.fine', { link: `<a href="https://kolkatatrafficpolice.gov.in/" target="_blank" rel="noopener">${t('park.kp')}</a>` })}</p>`;
  }
  panel.innerHTML = `<div class="seg" role="tablist">${segs.map(([k, ic, label]) => `<button role="tab" data-seg="${k}" aria-selected="${e.seg === k}">${icon(ic, 'sm')} ${label}</button>`).join('')}</div>
    <div class="chips" id="exploreZones">${zoneChips(e.zone)}</div>${body}`;
  wire(panel);
}

function wire(panel) {
  panel.onclick = (ev) => {
    const seg = ev.target.closest('[data-seg]')?.dataset.seg; if (seg) { S.explore.seg = seg; return render(); }
    const z = ev.target.closest('[data-z]')?.dataset.z; if (z) { S.explore.zone = z; return render(); }
    const f = ev.target.closest('[data-f]')?.dataset.f; if (f) { S.explore.food.has(f) ? S.explore.food.delete(f) : S.explore.food.add(f); return render(); }
    const place = ev.target.closest('[data-place]')?.dataset.place; if (place) return openPlace(place);
    if (ev.target.closest('#carClear')) { S.car = null; store.set('car', null); return render(); }
    if (ev.target.closest('#carSave')) return getFix().then((p) => { S.car = { lat: p.lat, lng: p.lng, ts: Date.now() }; store.set('car', S.car); toast(t('car.savedToast')); render(); }).catch(() => toast(t('loc.fail')));
  };
  const hr = $('#hourRange', panel);
  if (hr) hr.oninput = () => { S.hour = +hr.value; const y = window.scrollY; render(); window.scrollTo(0, y); $('#hourRange')?.focus(); };
  const so = $('#sortSelect', panel);
  if (so) so.onchange = () => {
    S.explore.sort = so.value;
    if (so.value === 'near' && !S.me) getFix().then(() => render()).catch(() => toast(t('loc.fail'))); else render();
  };
}

registerView('explore', { render, onShow: () => setTimeout(() => map?.invalidateSize(), 60) });
export const exploreMap = () => map;
export const refreshExplore = () => S.view === 'explore' && render();
