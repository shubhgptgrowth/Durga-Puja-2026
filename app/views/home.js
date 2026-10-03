/* Home: a simple start screen. "What would you like to do?" tasks, areas to pick, and ready-made routes. */
import { hav, fmtCount, searchEntries } from '../core.js';
import { S, G, idx, t, store, community, ll, nm, zn, zs, dn, zoneOf, esc, dist, todayKey, btn, icon, bnDigits } from '../state.js';
import { $, go, rerender, toast, getFix, registerView } from '../ui.js';
import { openPlace } from '../sheets.js';
import { showTrail } from './plan.js';
import { setExplore } from './explore.js';
import { selectArea, rname } from '../filters.js';

let searchIndex = null;
function buildIndex() {
  const e = [];
  for (const p of G.data.pandals) e.push({ id: p.id, kind: 'pandal', names: [p.name, p.name_bn || ''], extra: [...p.tags, idx.zone[p.zone].name], boost: p.popularity });
  for (const f of G.data.food) e.push({ id: f.id, kind: 'food', names: [f.name], extra: [...f.dishes, f.type] });
  for (const p of G.data.parking) e.push({ id: p.id, kind: 'parking', names: [p.name], extra: ['parking', 'park', 'পার্কিং'] });
  for (const z of G.data.zones) e.push({ id: z.id, kind: 'zone', names: [z.name, z.short, z.name_bn || '', z.short_bn || ''], extra: [], boost: 10 });
  return e;
}

const fmtDate = (d) => new Date(d.date + 'T00:00:00').toLocaleDateString(S.prefs.lang === 'bn' ? 'bn-IN' : 'en-IN', { weekday: 'short', day: 'numeric', month: 'short' });

/* A short "today" strip: which puja day the crowd times are for, and the one tip that matters. */
function heroHtml() {
  const sel = idx.day[S.day], today = G.data.meta.days.find((d) => d.date === todayKey());
  const shashthi = new Date(idx.day.shashthi.date + 'T00:00:00'), now = new Date(); now.setHours(0, 0, 0, 0);
  const diff = Math.round((shashthi - now) / 864e5);
  const eyebrow = today ? t('h.today') : diff > 0 ? t('h.countdown', { n: bnDigits(diff) }) : t('h.planning');
  return `<div class="hero compact">
    <div class="hero-top"><div><div class="eyebrow">${eyebrow}</div>
      <h2>${t('h.dayLine', { day: esc(dn(sel)), date: fmtDate(sel) })}</h2></div>
      <button class="hero-link" data-q="day">${t('h.changeDay')}</button></div>
    <p>${t('h.simpleTip')}</p>
  </div>`;
}

const TASKS = [
  ['near', 'locate'], ['plan', 'route'], ['famous', 'star'],
  ['food', 'food'], ['park', 'car'], ['photos', 'camera'],
];

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
  const busy = Object.values(st).filter((s) => s.last_hour > 0 || s.today > 0)
    .sort((a, b) => b.last_hour - a.last_hour || b.today - a.today).slice(0, 8)
    .map((s) => idx.pandal[s.place_id]).filter(Boolean);
  const showIntro = !store.get('introDone', false);

  el.innerHTML = `
    ${heroHtml()}
    <section class="section first"><div class="section-head"><h2>${t('h.whatToDo')}</h2></div>
      <div class="tasks">${TASKS.map(([k, ic]) => `<button class="task" data-q="${k}">
        <span class="task-ic">${icon(ic)}</span><span class="task-t">${t('task.' + k)}</span><span class="task-s">${t('task.' + k + 'Sub')}</span></button>`).join('')}</div>
    </section>

    <div class="search" role="search">
      ${icon('search')}
      <input id="homeSearch" type="search" autocomplete="off" placeholder="${t('h.search')}" aria-label="${t('h.search')}">
      <ul class="results" id="homeResults" role="listbox"></ul>
    </div>

    ${showIntro ? `<section class="intro" aria-label="${t('h.introTitle')}">
      <div class="intro-head"><h2>${t('h.introTitle')}</h2><button class="icon-btn" data-q="introClose" aria-label="${t('h.introClose')}">×</button></div>
      <ol><li>${t('h.intro1')}</li><li>${t('h.intro2')}</li><li>${t('h.intro3')}</li></ol>
    </section>` : ''}

    <section class="section"><div class="section-head"><div><h2>${t('h.pickArea')}</h2><p class="sub">${t('h.pickAreaSub')}</p></div></div>
      <div class="regions">${G.data.regions.map((r) => {
        const n = r.zone_ids.reduce((c, id) => c + (idx.zone[id]?.pandal_ids.length || 0), 0);
        const areas = r.zone_ids.map((id) => idx.zone[id]).filter(Boolean).map(zs).join(' · ');
        return `<button class="region" data-hr="${r.id}" style="--zc:${r.color}"><span class="region-n">${esc(rname(r))}</span><span class="region-c">${t('h.pandalsN', { n })}</span><span class="region-a">${esc(areas)}</span></button>`;
      }).join('')}</div>
    </section>

    ${busy.length ? `<section class="section"><div class="section-head"><div><h2>${t('h.trending')}</h2><p class="sub">${t('h.trendingSub')}</p></div></div>
      <div class="hscroll">${busy.map((p) => { const s = st[p.id]; return miniPandal(p, s.last_hour
        ? `<span class="pill live"><span class="dot"></span>${t('c.liveN', { n: fmtCount(s.last_hour) })}</span>`
        : `<span class="pill">${icon('people', 'sm')} ${t('c.todayN', { n: fmtCount(s.today) })}</span>`); }).join('')}</div></section>` : ''}

    <section class="section"><div class="section-head"><div><h2>${t('h.trails')}</h2><p class="sub">${t('h.trailsSub')}</p></div><button class="link-btn" data-q="plan">${t('h.seeAll')}</button></div>
      <div class="list">${G.data.itineraries.slice(0, 3).map((it) => `<div class="card trail" data-trail="${it.id}" ${btn()}>
        <h3>${esc((S.prefs.lang === 'bn' && it.name_bn) || it.name)}</h3>
        <div class="row"><span>${t('it.pandals', { n: it.pandal_count })}</span><span>${it.totals.walk_km} km</span><span>${dn(idx.day[it.day])} · ${it.start_time}</span></div></div>`).join('')}</div></section>
    <p class="fine center" style="margin:24px 16px 0">${t('p.disclaimer')}</p>`;

  wire(el);
}

function wire(el) {
  el.onclick = (e) => {
    const q = e.target.closest('[data-q]')?.dataset.q;
    if (q === 'plan') return go('plan');
    if (q === 'near') { setExplore({ seg: 'pandals', sort: 'near', region: 'all', area: 'all' }); go('explore'); if (!S.me) getFix().then(() => rerender()).catch(() => toast(t('loc.fail'))); return; }
    if (q === 'famous') { setExplore({ seg: 'pandals', sort: 'popular', region: 'all', area: 'all' }); return go('explore'); }
    if (q === 'food') { setExplore({ seg: 'food' }); return go('explore'); }
    if (q === 'park') { setExplore({ seg: 'parking' }); return go('explore'); }
    if (q === 'photos') return go('moments');
    if (q === 'day') { const d = $('#daySelect'); d.focus(); d.showPicker?.(); return; }
    if (q === 'introClose') { store.set('introDone', true); return render(); }
    const place = e.target.closest('[data-place]')?.dataset.place; if (place) return openPlace(place);
    const hr = e.target.closest('[data-hr]')?.dataset.hr; if (hr) { setExplore({ seg: 'pandals', region: hr, area: 'all' }); return go('explore'); }
    const trail = e.target.closest('[data-trail]')?.dataset.trail; if (trail) { go('plan'); return showTrail(trail); }
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
