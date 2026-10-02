/* Home: the at-a-glance overview. */
import { hav, fmtCount, searchEntries } from '../core.js';
import {
  S, G, idx, t, community, ll, nm, zn, zs, dn, zoneOf, esc, km, dist, ampm, crowdNow, todayKey, btn, icon, stepsFor, bnDigits,
} from '../state.js';
import { $, go, registerView } from '../ui.js';
import { openPlace, crowdPill, thumbHtml, momentSheet, momentCache } from '../sheets.js';
import { showTrail } from './plan.js';
import { setExplore } from './explore.js';
import { selectArea, rname } from '../filters.js';

let homeRegion = null;

let searchIndex = null;
function buildIndex() {
  const e = [];
  for (const p of G.data.pandals) e.push({ id: p.id, kind: 'pandal', names: [p.name, p.name_bn || ''], extra: [...p.tags, idx.zone[p.zone].name], boost: p.popularity });
  for (const f of G.data.food) e.push({ id: f.id, kind: 'food', names: [f.name], extra: [...f.dishes, f.type] });
  for (const p of G.data.parking) e.push({ id: p.id, kind: 'parking', names: [p.name], extra: ['parking', 'park', 'পার্কিং'] });
  for (const z of G.data.zones) e.push({ id: z.id, kind: 'zone', names: [z.name, z.short, z.name_bn || '', z.short_bn || ''], extra: [], boost: 10 });
  return e;
}

function heroHtml() {
  const days = G.data.meta.days, today = days.find((d) => d.date === todayKey()), sel = idx.day[S.day];
  const shashthi = new Date(idx.day.shashthi.date + 'T00:00:00'), now = new Date(); now.setHours(0, 0, 0, 0);
  const diff = Math.round((shashthi - now) / 864e5);
  const eyebrow = today ? t('h.today') : diff > 0 ? t('h.countdown', { n: bnDigits(diff) }) : t('h.planning');
  const hf = G.data.meta.model.hour_factors;
  const quiet = [...hf.keys()].filter((h) => h >= 5 && h <= 9).sort((a, b) => hf[a] - hf[b])[0];
  return `<div class="hero">
    <div class="eyebrow">${eyebrow}</div>
    <h2>${esc(dn(sel))} · ${new Date(sel.date + 'T00:00:00').toLocaleDateString(S.prefs.lang === 'bn' ? 'bn-IN' : 'en-IN', { weekday: 'short', day: 'numeric', month: 'short' })}</h2>
    <p>${t('h.tip', { quiet: ampm(quiet), peak: `${ampm(20)}–${ampm(0)}` })}</p>
    <div class="hero-row">
      <span class="hero-chip">${icon('people', 'sm')} ${t('h.pandalsN', { n: G.data.pandals.length })}</span>
      <span class="hero-chip">${icon('food', 'sm')} ${t('h.foodN', { n: G.data.food.length })}</span>
      <span class="hero-chip">${icon('map', 'sm')} ${t('h.zonesN', { n: G.data.zones.length })}</span>
    </div>
  </div>`;
}

function miniPandal(p, extra) {
  const z = zoneOf(p.zone);
  return `<div class="mini" data-place="${p.id}" style="--zc:${z.color}" ${btn(`aria-label="${esc(nm(p))}"`)}>
    <div class="nm">${esc(nm(p))}</div>
    <div class="meta">${esc(zs(z))}${S.me ? ` · ${dist(hav(S.me, ll(p)))}` : ''}</div>
    <div>${extra}</div>
  </div>`;
}

function render() {
  const el = $('#view-home');
  const st = community.enabled ? community.stats.byPlace : {};
  const trending = Object.values(st).filter((s) => s.last_hour > 0 || s.today > 0)
    .sort((a, b) => b.last_hour - a.last_hour || b.today - a.today).slice(0, 8)
    .map((s) => idx.pandal[s.place_id] || idx.food[s.place_id]).filter(Boolean);
  const goodNow = G.data.pandals.filter((p) => p.popularity >= 4)
    .map((p) => [p, crowdNow(p)]).sort((a, b) => a[1] - b[1] || b[0].popularity - a[0].popularity).slice(0, 8);
  const near = S.me ? G.data.pandals.map((p) => [p, hav(S.me, ll(p))]).sort((a, b) => a[1] - b[1]).slice(0, 6) : [];

  el.innerHTML = `
    ${heroHtml()}
    <div class="search" role="search">
      ${icon('search')}
      <input id="homeSearch" type="search" autocomplete="off" placeholder="${t('h.search')}" aria-label="${t('h.search')}">
      <ul class="results" id="homeResults" role="listbox"></ul>
    </div>
    <div class="quick">
      <button data-q="plan">${icon('route')}${t('h.qPlan')}</button>
      <button data-q="near">${icon('locate')}${t('h.qNear')}</button>
      <button data-q="food">${icon('food')}${t('h.qFood')}</button>
      <button data-q="park">${icon('car')}${t('h.qPark')}</button>
    </div>

    ${trending.length ? `<section class="section"><div class="section-head"><div><h2>${t('h.trending')}</h2><p class="sub">${t('h.trendingSub')}</p></div></div>
      <div class="hscroll">${trending.map((p) => { const s = st[p.id]; return miniPandal(p, s.last_hour
        ? `<span class="pill live"><span class="dot"></span>${t('c.liveN', { n: fmtCount(s.last_hour) })}</span>`
        : `<span class="pill">${icon('people', 'sm')} ${t('c.todayN', { n: fmtCount(s.today) })}</span>`); }).join('')}</div></section>` : ''}

    ${near.length ? `<section class="section"><div class="section-head"><h2>${t('h.near')}</h2></div>
      <div class="hscroll">${near.map(([p]) => miniPandal(p, crowdPill(crowdNow(p)))).join('')}</div></section>` : ''}

    <section class="section"><div class="section-head"><div><h2>${t('h.goodNow')}</h2><p class="sub">${t('h.goodNowSub', { time: ampm(S.hour), day: dn(idx.day[S.day]) })}</p></div><button class="link-btn" data-q="explore">${t('h.seeAll')}</button></div>
      <div class="hscroll">${goodNow.map(([p, c]) => miniPandal(p, crowdPill(c))).join('')}</div></section>

    <section class="section"><div class="section-head"><h2>${t('h.zones')}</h2></div>
      <div class="chips">${G.data.regions.map((r) => `<button class="chip" data-hr="${r.id}" aria-pressed="${r.id === (homeRegion ||= G.data.regions[0].id)}"><span class="dot" style="background:${r.color}"></span>${esc(rname(r))} · ${r.zone_ids.reduce((n, id) => n + (idx.zone[id]?.pandal_ids.length || 0), 0)}</button>`).join('')}</div>
      <div class="zone-list">${G.data.zones.filter((z) => z.region === homeRegion).map((z) => `<div class="zone-card" data-zone="${z.id}" style="--zc:${z.color}" ${btn(`aria-label="${esc(zn(z))}"`)}>
        <span class="bar"></span>
        <div><h3>${esc(zn(z))}</h3><p>${esc(z.vibe)}</p>
          <div class="meta"><span>${t('z.pandals', { n: z.pandal_ids.length })}</span><span>${t('z.loop', { km: km(z.route.walk_m) })}</span><span>${t('z.steps', { n: fmtCount(stepsFor(z.route.walk_m)) })}</span><span class="pill car-${z.car_advisory}">${t('car.' + z.car_advisory)}</span></div></div>
        ${icon('chev')}</div>`).join('')}</div></section>

    ${community.enabled ? `<section class="section"><div class="section-head"><h2>${t('h.moments')}</h2><button class="link-btn" data-q="moments">${t('h.seeAll')}</button></div><div id="homeMoments" class="grid-photos"></div></section>` : ''}

    <section class="section"><div class="section-head"><h2>${t('h.trails')}</h2><button class="link-btn" data-q="plan">${t('h.seeAll')}</button></div>
      <div class="list">${G.data.itineraries.slice(0, 3).map((it) => `<div class="card trail" data-trail="${it.id}" ${btn()}>
        <h3>${esc((S.prefs.lang === 'bn' && it.name_bn) || it.name)}</h3>
        <div class="row"><span>${t('it.pandals', { n: it.pandal_count })}</span><span>${it.totals.walk_km} km</span><span>${dn(idx.day[it.day])} · ${it.start_time}</span></div></div>`).join('')}</div></section>
    <p class="fine center" style="margin:24px 16px 0">${t('p.disclaimer')}</p>`;

  wire(el);
  if (community.enabled) loadHomeMoments();
}

async function loadHomeMoments() {
  const box = $('#homeMoments'); if (!box) return;
  try {
    const items = await community.feed({ limit: 6 });
    momentCache.push(...items);
    box.innerHTML = items.length ? items.map(thumbHtml).join('') : `<p class="fine" style="grid-column:1/-1">${t('m.empty')}</p>`;
  } catch { box.innerHTML = `<p class="fine" style="grid-column:1/-1">${t('m.offline')}</p>`; }
}

function wire(el) {
  el.onclick = (e) => {
    const q = e.target.closest('[data-q]')?.dataset.q;
    if (q === 'plan') return go('plan');
    if (q === 'explore') { setExplore({ seg: 'pandals', sort: 'quiet' }); return go('explore'); }
    if (q === 'near') { setExplore({ seg: 'pandals', sort: 'near' }); return go('explore'); }
    if (q === 'food') { setExplore({ seg: 'food' }); return go('explore'); }
    if (q === 'park') { setExplore({ seg: 'parking' }); return go('explore'); }
    if (q === 'moments') return go('moments');
    const place = e.target.closest('[data-place]')?.dataset.place; if (place) return openPlace(place);
    const hr = e.target.closest('[data-hr]')?.dataset.hr; if (hr) { homeRegion = hr; const y = window.scrollY; render(); return window.scrollTo(0, y); }
    const zone = e.target.closest('[data-zone]')?.dataset.zone; if (zone) { setExplore({ seg: 'pandals', ...selectArea(zone) }); return go('explore'); }
    const trail = e.target.closest('[data-trail]')?.dataset.trail; if (trail) { go('plan'); return showTrail(trail); }
    const m = e.target.closest('[data-moment]')?.dataset.moment; if (m) return momentSheet(momentCache.find((x) => x.id === m));
    const r = e.target.closest('[data-result]'); if (r) return pickResult(r.dataset.kind, r.dataset.result);
  };
  const input = $('#homeSearch', el), out = $('#homeResults', el);
  input.oninput = () => {
    searchIndex ||= buildIndex();
    const res = searchEntries(searchIndex, input.value);
    const kindIcon = { pandal: 'star', food: 'food', parking: 'car', zone: 'map' };
    out.innerHTML = res.map((r) => {
      const p = r.kind === 'zone' ? idx.zone[r.id] : idx[r.kind][r.id];
      const name = r.kind === 'zone' ? zn(p) : r.kind === 'pandal' ? nm(p) : p.name;
      const meta = r.kind === 'zone' ? t('z.pandals', { n: p.pandal_ids.length }) : `${t('kindLabel.' + r.kind)} · ${esc(zs(idx.zone[p.zone]))}`;
      return `<li data-result="${r.id}" data-kind="${r.kind}" ${btn()}><span class="kind">${icon(kindIcon[r.kind], 'sm')}</span><span><div class="nm">${esc(name)}</div><div class="meta">${meta}</div></span></li>`;
    }).join('') || (input.value.trim().length >= 2 ? `<li class="muted">${t('h.noResults')}</li>` : '');
  };
}
function pickResult(kind, id) {
  if (kind === 'zone') { setExplore({ seg: 'pandals', ...selectArea(id) }); return go('explore'); }
  openPlace(id);
}

registerView('home', { render });
