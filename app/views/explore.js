/* Explore: Pandals / Food / Parking, one row of filters, and the list. */
import { hav, isOpen, pandalFilter, stationOptions } from '../core.js';
import {
  S, G, idx, t, store, community, ll, nm, zn, zs, zoneOf, esc, dist, ampm, dn, crowdNow, btn, icon, loc,
} from '../state.js';
import { $, registerView, getFix, toast } from '../ui.js';
import { offerChip, featuredFirst } from '../offers.js';
import { openPlace, crowdPill, statsHtml, ratingHtml, dirUrl, openHtml, costHtml, dietMarks, themeTitle, awardPill, vibePill } from '../sheets.js';
import { visitedToday } from '../actions.js';
import { track } from '../analytics.js';
import { carCardHtml, carClick } from '../car.js';
import { foodPhoto, tilePhoto, photoBg, photosOn } from '../photos.js';
import { dietMatch, DIETS } from '../foodinfo.js';
import { areaSelectHtml, setAreaValue, inArea, areasOf } from '../filters.js';

let moreOpen = false;

export function setExplore(patch) { Object.assign(S.explore, patch); }

function pandalItem(p) {
  const z = zoneOf(p.zone), c = crowdNow(p);
  return `<li class="item ${visitedToday(p.id) ? 'visited' : ''}" data-place="${p.id}" ${btn(`aria-label="${esc(nm(p))}"`)}>
    <h3 class="nm">${esc(nm(p))}</h3>
    <div class="side"><span class="score">${icon('star', 'sm fill')}${p.popularity}</span>${statsHtml(p.id, { compact: true })}</div>
    <div class="meta">${esc(zs(z))}${S.me ? ` · ${dist(hav(S.me, ll(p)))}` : ''} · ${icon('metro', 'sm')} ${esc(p.nearest_metro.name)}</div>
    ${p.theme_2026 ? `<div class="theme-line"><b>${t('p.theme2026')}</b>${esc(themeTitle(p.theme_2026))}</div>` : ''}
    <div class="status">${vibePill(p)}${awardPill(p)}${crowdPill(c)}</div>
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
      ${offerChip(f.id)}
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
  const year = G.data.meta.year;
  const list = G.data.pandals.filter((p) => inArea(e, p.zone) && pandalFilter(p, e, year));
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
  return featuredFirst(list);   // paid featured offers first, labelled "Sponsored" on the tile
}
const parkList = (e) => G.data.parking.filter((p) => inArea(e, p.zone) || (idx.zone[p.zone] == null && e.region === 'all'));

/** Section tabs plus ONE row of filters: the area dropdown, then sort (pandals) or diet/price chips (food). */
function barHtml(e) {
  const segs = [['pandals', 'star', t('seg.pandals')], ['food', 'food', t('seg.food')], ['parking', 'car', t('seg.parking')]];
  const extra = e.seg === 'pandals'
    ? `<select id="sortSelect" aria-label="${t('sort.label')}">${['popular', 'near', ...(community.enabled ? ['live'] : []), 'quiet'].map((k) => `<option value="${k}" ${e.sort === k ? 'selected' : ''}>${t('sort.' + k)}</option>`).join('')}</select>`
    : e.seg === 'food' ? [...DIETS, 'sweets', 'street', 'open'].map((k) => `<button class="chip sm" data-f="${k}" aria-pressed="${e.food.has(k)}">${k === 'veg' ? '<span class="veg-mark sm" aria-hidden="true"></span>' : ''}${t('ff.' + k)}</button>`).join('') : '';
  const n = { pandals: G.data.pandals.length, food: G.data.food.length, parking: G.data.parking.length };
  const em = { pandals: '🛕', food: '🍛', parking: '🅿️' };
  const img = photosOn() ? { pandals: 'img/hero-1.jpg', food: tilePhoto('food'), parking: tilePhoto('parking') } : {}; // saved in the app, so they show on weak networks
  return `<h2 class="ex-title">${t('ex.title')}</h2>
    <div class="seg photo-seg" role="tablist">${segs.map(([k, , label]) => `<button role="tab" data-seg="${k}" aria-selected="${e.seg === k}" class="${img[k] ? 'has-img' : ''}">
      ${photoBg(img[k], 'seg-img')}<span class="seg-em" aria-hidden="true">${em[k]}</span><span class="seg-l">${label}</span><span class="seg-n">${n[k]}</span></button>`).join('')}</div>
    <div class="filter-row ${e.seg}">${areaSelectHtml(e, 'areaSelect')}${extra}</div>`;
}

/** Pandals only: heritage and award chips plus a metro station picker. In the list, not the sticky bar, so it scrolls away. */
const moreFiltersHtml = (e) => `<div class="filter-row pandals2">
      ${['heritage', 'award'].map((k) => `<button class="chip sm" data-only="${k}" aria-pressed="${e.only.has(k)}">${t('ff.' + k)}</button>`).join('')}
      <select id="stationSelect" aria-label="${t('st.label')}"><option value="all">${t('st.all')}</option>${stationOptions(G.data.pandals).map((m) => `<option value="${m.id}" ${e.station === m.id ? 'selected' : ''}>${esc(m.name)} (${m.n})</option>`).join('')}</select></div>`;

function listHtml(e, list) {
  if (e.seg === 'pandals') {
    const z = e.area !== 'all' ? zoneOf(e.area) : null;
    return `${z ? `<div class="notice ${z.car_advisory}"><b>${esc(zn(z))}</b><span>${esc(z.vibe)}</span><span>${t('car.' + z.car_advisory)} · ${esc(z.walk_tip)}</span></div>` : ''}
      ${moreFiltersHtml(e)}
      <div class="toolbar"><span>${t('list.count', { n: list.length })}</span>${e.station !== 'all' || e.only.size ? `<button class="link-btn" data-clear>${t('ff.clear')}</button>` : ''}</div>
      ${list.length ? '' : `<p class="empty">${t('ff.none')}</p>`}
      <ul class="list">${list.map(pandalItem).join('')}</ul>
      <details class="more" ${S.hour !== new Date().getHours() || moreOpen ? 'open' : ''}><summary>${icon('clock', 'sm')} ${t('crowd.other')}</summary>
        <div class="time-row"><label for="crowdDay">${t('f.day')}</label><select id="crowdDay">${G.data.meta.days.map((d) => `<option value="${d.id}" ${S.day === d.id ? 'selected' : ''}>${esc(dn(d))}</option>`).join('')}</select></div>
        <div class="time-row"><label for="hourRange">${t('crowd.at')}</label><input type="range" id="hourRange" min="0" max="23" value="${S.hour}"><strong>${ampm(S.hour)}</strong></div></details>`;
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
    <div class="metro-chips">${near.map((s) => `<span class="mc"><span class="line-${s.line}">●</span> ${esc(s.name)}</span>`).join('')}</div>
    <p class="tiny-note">${t('park.fine', { link: `<a href="https://kolkatatrafficpolice.gov.in/" target="_blank" rel="noopener">${t('park.kp')}</a>` })}</p>`;
}

function render() {
  const e = S.explore, view = $('#view-explore');
  const list = e.seg === 'pandals' ? pandalList(e) : e.seg === 'food' ? foodList(e) : parkList(e);
  $('#exploreBar').innerHTML = barHtml(e);
  $('#explorePanel').innerHTML = listHtml(e, list);
  wire(view);
}

function wire(view) {
  view.onclick = (ev) => {
    const seg = ev.target.closest('[data-seg]')?.dataset.seg; if (seg) { S.explore.seg = seg; track('filter', { d: 'seg:' + seg }); return render(); }
    const only = ev.target.closest('[data-only]')?.dataset.only;
    if (only) { S.explore.only.has(only) ? S.explore.only.delete(only) : S.explore.only.add(only); track('filter', { d: 'only:' + only }); return render(); }
    if (ev.target.closest('[data-clear]')) { S.explore.only.clear(); S.explore.station = 'all'; return render(); }
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
  const ss = $('#stationSelect', view);
  if (ss) ss.onchange = () => { S.explore.station = ss.value; track('filter', { d: 'station:' + ss.value }); render(); };
  const so = $('#sortSelect', view);
  if (so) so.onchange = () => {
    S.explore.sort = so.value; track('filter', { d: 'sort:' + so.value });
    if (so.value === 'near' && !S.me) getFix().then(() => render()).catch(() => toast(t('loc.fail'))); else render();
  };
}

registerView('explore', { render });
export const refreshExplore = () => S.view === 'explore' && render();
