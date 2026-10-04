/* Explore (the Map tab): Pandals / Food / Parking, one row of filters, and a full-screen map or a list. */
import { hav, isOpen } from '../core.js';
import {
  S, G, idx, t, store, community, ll, nm, zn, zs, zoneOf, esc, dist, ampm, dn, crowdNow, btn, icon, loc,
} from '../state.js';
import { $, registerView, makeMap, pinIcon, getFix, toast } from '../ui.js';
import { openPlace, crowdPill, statsHtml, ratingHtml, dirUrl, openHtml, costHtml, dietMarks } from '../sheets.js';
import { visitedToday } from '../actions.js';
import { track } from '../analytics.js';
import { carCardHtml, carClick } from '../car.js';
import { foodPhoto, tilePhoto, photoBg, photosOn } from '../photos.js';
import { dietMatch, DIETS } from '../foodinfo.js';
import { areaSelectHtml, setAreaValue, inArea, areasOf, bboxOf } from '../filters.js';

let map = null, layers = {}, meMarker = null, moreOpen = false;
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
function fitZone(force = false) {
  if (!map || S.explore.mode !== 'map') return;
  const key = S.explore.region + '/' + S.explore.area;
  if (key === lastFit && !force) return; lastFit = key;
  const bb = bboxOf(S.explore);
  if (!bb) map.setView([22.56, 88.37], 12);
  else map.fitBounds(bb, { padding: [30, 30], maxZoom: 16 });
}


function pandalItem(p) {
  const z = zoneOf(p.zone), c = crowdNow(p);
  return `<li class="item ${visitedToday(p.id) ? 'visited' : ''}" data-place="${p.id}" ${btn(`aria-label="${esc(nm(p))}"`)}>
    <h3 class="nm">${esc(nm(p))}</h3>
    <div class="side"><span class="score">${icon('star', 'sm fill')}${p.popularity}</span>${statsHtml(p.id, { compact: true })}</div>
    <div class="meta">${esc(zs(z))}${S.me ? ` · ${dist(hav(S.me, ll(p)))}` : ''} · 🚇 ${esc(p.nearest_metro.name)}</div>
    <div class="status">${crowdPill(c)}<span class="pill" title="${t('card.bestHint')}">${icon('clock', 'sm')} ${t('card.best', { slot: t('slot.' + p.best_slot) })}</span></div>
  </li>`;
}
function foodItem(f) {
  const near = f.near_pandals.slice(0, 2).map((id) => nm(idx.pandal[id]));
  const marks = dietMarks(f);
  const ph = foodPhoto(f);
  return `<li class="item food-item ${ph ? 'has-thumb' : ''} ${visitedToday(f.id) ? 'visited' : ''}" data-place="${f.id}" ${btn(`aria-label="${esc(f.name)}"`)}>
    ${ph ? `<div class="fi-thumb">${photoBg(ph, 'fi-img')}</div>` : ''}
    <div class="main">
      <h3 class="nm">${esc(f.name)}</h3>
      <div class="meta">${esc(f.dishes.slice(0, 3).join(' · '))}</div>
      ${openHtml(f)}
      ${near.length ? `<div class="near">📍 ${t('food.near', { list: esc(near.join(', ')) })}</div>` : ''}
    </div>
    <div class="side">
      ${ratingHtml(f.id, true)}
      ${costHtml(f)}
      ${statsHtml(f.id, { compact: true })}
      ${marks ? `<div class="marks">${marks}</div>` : ''}
    </div>
  </li>`;
}


function pandalList(e) {
  const list = G.data.pandals.filter((p) => inArea(e, p.zone));
  if (e.sort === 'popular') list.sort((a, b) => b.popularity - a.popularity || crowdNow(a) - crowdNow(b));
  if (e.sort === 'quiet') list.sort((a, b) => crowdNow(a) - crowdNow(b) || b.popularity - a.popularity);
  if (e.sort === 'near' && S.me) list.sort((a, b) => hav(S.me, ll(a)) - hav(S.me, ll(b)));
  if (e.sort === 'live') list.sort((a, b) => (community.statFor(b.id)?.last_hour || 0) - (community.statFor(a.id)?.last_hour || 0) || b.popularity - a.popularity);
  return list;
}
function foodList(e) {
  const F = e.food;
  const list = G.data.food.filter((f) => inArea(e, f.zone)
    && dietMatch(f, F)
    && (!F.has('sweets') || f.type === 'sweets' || f.type === 'drinks') && (!F.has('street') || f.type === 'street')
    && (!F.has('open') || isOpen(f.hours)));
  if (S.me) list.sort((a, b) => hav(S.me, ll(a)) - hav(S.me, ll(b)));
  return list;
}
const parkList = (e) => G.data.parking.filter((p) => inArea(e, p.zone) || (idx.zone[p.zone] == null && e.region === 'all'));

/** Section tabs plus ONE row of filters: the area dropdown, then sort (pandals) or diet/price chips (food). */
function barHtml(e) {
  const segs = [['pandals', 'star', t('seg.pandals')], ['food', 'food', t('seg.food')], ['parking', 'car', t('seg.parking')]];
  const extra = e.seg === 'pandals'
    ? `<select id="sortSelect" aria-label="${t('sort.label')}">${['popular', 'quiet', 'near', ...(community.enabled ? ['live'] : [])].map((k) => `<option value="${k}" ${e.sort === k ? 'selected' : ''}>${t('sort.' + k)}</option>`).join('')}</select>`
    : e.seg === 'food' ? [...DIETS, 'sweets', 'street', 'open'].map((k) => `<button class="chip sm" data-f="${k}" aria-pressed="${e.food.has(k)}">${k === 'veg' ? '<span class="veg-mark sm" aria-hidden="true"></span>' : ''}${t('ff.' + k)}</button>`).join('') : '';
  const n = { pandals: G.data.pandals.length, food: G.data.food.length, parking: G.data.parking.length };
  const em = { pandals: '🛕', food: '🍛', parking: '🅿️' };
  const img = photosOn() ? { pandals: 'img/hero-1.jpg', food: tilePhoto('food'), parking: tilePhoto('parking') } : {}; // saved in the app, so they show on weak networks
  return `<h2 class="ex-title">${t('ex.title')}</h2>
    <div class="seg photo-seg" role="tablist">${segs.map(([k, , label]) => `<button role="tab" data-seg="${k}" aria-selected="${e.seg === k}" class="${img[k] ? 'has-img' : ''}">
      ${photoBg(img[k], 'seg-img')}<span class="seg-em" aria-hidden="true">${em[k]}</span><span class="seg-l">${label}</span><span class="seg-n">${n[k]}</span></button>`).join('')}</div>
    <div class="filter-row ${e.seg}">${areaSelectHtml(e, 'areaSelect')}${extra}</div>`;
}

function listHtml(e, list) {
  if (e.seg === 'pandals') {
    const z = e.area !== 'all' ? zoneOf(e.area) : null;
    return `${z ? `<div class="notice ${z.car_advisory}"><b>${esc(zn(z))}</b><span>${esc(z.vibe)}</span><span>${t('car.' + z.car_advisory)} · ${esc(z.walk_tip)}</span></div>` : ''}
      <div class="toolbar"><span>${t('list.count', { n: list.length })}</span></div>
      <details class="more" ${S.hour !== new Date().getHours() || moreOpen ? 'open' : ''}><summary>${icon('clock', 'sm')} ${t('crowd.other')}</summary>
        <div class="time-row"><label for="crowdDay">${t('f.day')}</label><select id="crowdDay">${G.data.meta.days.map((d) => `<option value="${d.id}" ${S.day === d.id ? 'selected' : ''}>${esc(dn(d))}</option>`).join('')}</select></div>
        <div class="time-row"><label for="hourRange">${t('crowd.at')}</label><input type="range" id="hourRange" min="0" max="23" value="${S.hour}"><strong>${ampm(S.hour)}</strong></div></details>
      <ul class="list">${list.map(pandalItem).join('')}</ul>`;
  }
  if (e.seg === 'food') return `<ul class="list">${list.map(foodItem).join('') || `<li class="empty">${t('food.none')}</li>`}</ul>`;
  const car = S.car, zl = areasOf(e).map(zoneOf), ids = zl.flatMap((z) => z.pandal_ids);
  const near = e.region === 'all' ? G.data.transit : G.data.transit.filter((s) => ids.some((id) => hav(ll(s), ll(idx.pandal[id])) < 2500));
  return `${carCardHtml()}
    ${e.region === 'all' ? '' : zl.map((z) => `<div class="notice ${z.car_advisory}"><b>${esc(zs(z))}: ${t('adv.' + z.car_advisory)}</b><span>${esc(z.walk_tip)}</span></div>`).join('')}
    <div class="section-head" style="margin-top:16px"><h2>${t('h.parking')}</h2></div>
    <ul class="list">${list.map((p) => `<li class="item park-item" data-place="${p.id}" ${btn(`aria-label="${esc(p.name)}"`)}>
      <div class="pk-ic" aria-hidden="true">P</div>
      <div class="main"><h3 class="nm">${esc(p.name)}</h3>
        <div class="meta">${t('kind.' + p.kind)} · ${t('cap.' + p.capacity)}</div>
        <div class="fine">${esc(p.note)}</div></div>
      <div class="side"><span class="park-cost"><b>${esc(p.rate_hint)}</b><small>${t('park.costLbl')}</small></span></div></li>`).join('') || `<li class="empty">${t('park.none')}</li>`}</ul>
    <div class="section-head" style="margin-top:16px"><h2>${t('h.transit')}</h2></div>
    <div class="chips wrap pad">${near.map((s) => `<span class="pill"><span class="line-${s.line}">●</span> ${esc(s.name)}</span>`).join('')}</div>
    <p class="fine pad" style="margin-top:12px">${t('park.fine', { link: `<a href="https://kolkatatrafficpolice.gov.in/" target="_blank" rel="noopener">${t('park.kp')}</a>` })}</p>`;
}

/** In map mode the map fills the space between the filter bar and the tab bar. */
function sizeMap() {
  const m = $('#map');
  if (!m || S.explore.mode !== 'map' || S.view !== 'explore') return;
  const tb = $('.tabbar')?.offsetHeight || 62;
  m.style.height = Math.max(260, window.innerHeight - m.getBoundingClientRect().top - tb) + 'px';
  map?.invalidateSize();
}

function render() {
  const e = S.explore, view = $('#view-explore');
  const prevMode = view.dataset.mode;
  view.dataset.mode = e.mode;
  ensureMap(); syncLayers(); drawMe();
  const list = e.seg === 'pandals' ? pandalList(e) : e.seg === 'food' ? foodList(e) : parkList(e);
  $('#exploreBar').innerHTML = barHtml(e);
  $('#explorePanel').innerHTML = e.mode === 'list' ? listHtml(e, list) : '';
  const noun = t(e.seg === 'pandals' ? 'list.count' : e.seg === 'food' ? 'list.countFood' : 'list.countPark', { n: list.length });
  $('#modeBtn').innerHTML = e.mode === 'map' ? `${icon('list', 'sm')} ${t('mode.list')} · ${noun}` : `${icon('map', 'sm')} ${t('mode.map')}`;
  $('#modeBtn').dataset.to = e.mode === 'map' ? 'list' : 'map';
  if (e.mode === 'map') { sizeMap(); fitZone(prevMode !== 'map'); }
  wire(view);
}

function wire(view) {
  view.onclick = (ev) => {
    const seg = ev.target.closest('[data-seg]')?.dataset.seg; if (seg) { S.explore.seg = seg; track('filter', { d: 'seg:' + seg }); return render(); }
    if (ev.target.closest('#modeBtn')) { S.explore.mode = S.explore.mode === 'map' ? 'list' : 'map'; track('filter', { d: 'mode:' + S.explore.mode }); window.scrollTo(0, 0); return render(); }
    const f = ev.target.closest('[data-f]')?.dataset.f; if (f) { S.explore.food.has(f) ? S.explore.food.delete(f) : S.explore.food.add(f); track('filter', { d: 'food:' + f }); return render(); }
    const place = ev.target.closest('#explorePanel [data-place]')?.dataset.place; if (place) return openPlace(place);
    if (carClick(ev, render)) return;
  };
  const as = $('#areaSelect', view);
  if (as) as.onchange = () => { setAreaValue(S.explore, as.value); track('filter', { d: 'area:' + as.value }); render(); };
  const hr = $('#hourRange', view);
  if (hr) hr.oninput = () => { S.hour = +hr.value; const y = window.scrollY; render(); window.scrollTo(0, y); $('#hourRange')?.focus(); };
  const cd = $('#crowdDay', view);
  if (cd) cd.onchange = () => { moreOpen = true; S.day = cd.value; const y = window.scrollY; render(); window.scrollTo(0, y); };
  const so = $('#sortSelect', view);
  if (so) so.onchange = () => {
    S.explore.sort = so.value; track('filter', { d: 'sort:' + so.value });
    if (so.value === 'near' && !S.me) getFix().then(() => render()).catch(() => toast(t('loc.fail'))); else render();
  };
}

addEventListener('resize', () => sizeMap());
registerView('explore', { render, onShow: () => setTimeout(() => { sizeMap(); map?.invalidateSize(); }, 60) });
export const exploreMap = () => map;
export const refreshExplore = () => S.view === 'explore' && render();
