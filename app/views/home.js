/* Home: a simple start screen. "What would you like to do?" tasks, areas to pick, and ready-made routes. */
import { hav, fmtCount, searchEntries } from '../core.js';
import { S, G, idx, t, store, community, ll, nm, zn, zs, dn, zoneOf, esc, dist, todayKey, btn, icon, bnDigits, loc,
} from '../state.js';
import { $, go, rerender, toast, getFix, registerView } from '../ui.js';
import { openPlace } from '../sheets.js';
import { showTrail, dayPlanHtml, openDayPlan } from './plan.js';
import { setExplore } from './explore.js';
import { selectArea, rname } from '../filters.js';
import { radioCard } from '../radioCard.js';

let searchIndex = null;
function buildIndex() {
  const e = [];
  for (const p of G.data.pandals) e.push({ id: p.id, kind: 'pandal', names: [p.name, p.name_bn || ''], extra: [...p.tags, idx.zone[p.zone].name], boost: p.popularity });
  for (const f of G.data.food) e.push({ id: f.id, kind: 'food', names: [f.name], extra: [...f.dishes, f.type] });
  for (const p of G.data.parking) e.push({ id: p.id, kind: 'parking', names: [p.name], extra: ['parking', 'park', 'পার্কিং'] });
  for (const z of G.data.zones) e.push({ id: z.id, kind: 'zone', names: [z.name, z.short, z.name_bn || '', z.short_bn || ''], extra: [], boost: 10 });
  return e;
}

const fmtDate = (d) => new Date(d.date + 'T00:00:00').toLocaleDateString(loc(), { weekday: 'short', day: 'numeric', month: 'short' });

/* Ma Durga's three eyes (trinayani), the most recognisable image of the pujo, in ivory and kajal on sindoor. */
const EYE = 'M118 64 C 100 44, 62 40, 30 52 L 14 44 C 26 62, 62 82, 118 64 Z';
const EYES = `<svg class="trinayani" viewBox="0 0 240 104" aria-hidden="true">
  <defs><clipPath id="eyeL"><path d="${EYE}"/></clipPath>
    <radialGradient id="iris" cx=".4" cy=".35" r=".7"><stop offset="0" stop-color="#3B1D0E"/><stop offset=".55" stop-color="#140703"/><stop offset="1" stop-color="#000"/></radialGradient></defs>
  <g id="eyeHalf">
    <path d="M122 40 C 98 18, 56 16, 12 34 C 54 24, 96 26, 122 44 Z" fill="#14060A"/>
    <path d="${EYE}" fill="#FFF8EA"/>
    <g clip-path="url(#eyeL)"><circle cx="80" cy="60" r="15" fill="url(#iris)"/><circle cx="75" cy="55" r="3.4" fill="#fff" opacity=".9"/></g>
    <path d="${EYE}" fill="none" stroke="#14060A" stroke-width="4.5" stroke-linejoin="round"/>
    <path d="M118 66 C 96 80, 60 80, 22 58" fill="none" stroke="#D4A017" stroke-width="1.2" opacity=".8"/>
  </g>
  <use href="#eyeHalf" transform="translate(240 0) scale(-1 1)"/>
  <path d="M120 2 C 129 12, 129 26, 120 36 C 111 26, 111 12, 120 2 Z" fill="#FFF8EA" stroke="#14060A" stroke-width="3.5"/>
  <circle cx="120" cy="19" r="5.5" fill="#140703"/><circle cx="118.5" cy="17.5" r="1.4" fill="#fff"/>
  <circle cx="120" cy="44" r="4" fill="#C8102E" stroke="#D4A017" stroke-width="1.2"/>
  ${[-1, 1].map((d) => [0, 1, 2, 3, 4].map((k) => `<circle cx="${120 + d * (14 + k * 9)}" cy="${12 - k * 0.6 + k * k * 0.9}" r="${1.8 - k * 0.2}" fill="#E8B923"/>`).join('')).join('')}
</svg>`;

const span = () => { const o = { day: 'numeric' }, a = new Date(idx.day.shashthi.date + 'T00:00:00'), b = new Date(idx.day.dashami.date + 'T00:00:00');
  return `${a.toLocaleDateString(loc(), o)}–${b.toLocaleDateString(loc(), { day: 'numeric', month: 'short' })}`; };
/* The banner: greeting, the puja dates, and the one crowd tip that matters. */
function heroHtml() {
  const today = G.data.meta.days.find((d) => d.date === todayKey());
  const shashthi = new Date(idx.day.shashthi.date + 'T00:00:00'), now = new Date(); now.setHours(0, 0, 0, 0);
  const diff = Math.round((shashthi - now) / 864e5);
  const when = today ? t('h.todayIs', { day: esc(dn(today)) }) : diff > 0 ? t('h.countdown', { n: bnDigits(diff) }) : t('h.planning');
  return `<div class="hero sharad">
    ${EYES}
    <div class="sharad-text">
      <div class="sharad-greet" lang="bn">শুভ শারদীয়া</div>
      <div class="sharad-sub">${t('h.greetSub')}</div>
      <div class="sharad-when"><span>${when}</span><span class="sep">·</span><span>${span()}</span></div>
      <p>${t('h.simpleTip')}</p>
    </div>
    <div class="laalpaar" aria-hidden="true"></div>
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

  // The radio card is built once and moved in, never re-rendered, so its player keeps playing.
  if (!$('#homeTop', el)) el.innerHTML = '<div id="homeTop"></div><div id="radioSlot"></div><div id="homeRest"></div>';
  const slot = $('#radioSlot', el), card = radioCard();
  if (card.parentNode !== slot) slot.appendChild(card);
  $('#homeTop', el).innerHTML = `
    ${heroHtml()}
    <section class="section first"><div class="section-head"><h2>${t('h.whatToDo')}</h2></div>
      <div class="tasks">${TASKS.map(([k, ic]) => `<button class="task" data-q="${k}">
        <span class="task-ic">${icon(ic)}</span><span class="task-t">${t('task.' + k)}</span><span class="task-s">${t('task.' + k + 'Sub')}</span></button>`).join('')}</div>
    </section>

    <div class="search" role="search">
      ${icon('search')}
      <input id="homeSearch" type="search" autocomplete="off" placeholder="${t('h.search')}" aria-label="${t('h.search')}">
      <ul class="results" id="homeResults" role="listbox"></ul>
    </div>`;
  $('#homeRest', el).innerHTML = `

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

    <section class="section"><div class="section-head"><div><h2>${t('dp.title')}</h2><p class="sub">${t('dp.sub')}</p></div></div>
      ${dayPlanHtml()}</section>

    <section class="section"><div class="section-head"><div><h2>${t('h.trails')}</h2><p class="sub">${t('h.trailsSub')}</p></div><button class="link-btn" data-q="plan">${t('h.seeAll')}</button></div>
      <div class="list">${G.data.itineraries.slice(0, 3).map((it) => `<div class="card trail" data-trail="${it.id}" ${btn()}>
        <h3>${esc((S.prefs.lang === 'bn' && it.name_bn) || it.name)}</h3>
        <div class="row"><span>${t('it.pandals', { n: it.pandal_count })}</span><span>${it.totals.walk_km} km</span><span>${dn(idx.day[it.day])} · ${it.start_time}</span></div></div>`).join('')}</div></section>
    <p class="fine center" style="margin:24px 16px 0">${t('p.disclaimer')}</p>`;

  wire(el);
}

function wire(el) {
  el.onclick = (e) => {
    if (e.target.closest('.radio-card')) return;
    const dp = e.target.closest('[data-dayplan]')?.dataset.dayplan; if (dp) return openDayPlan(+dp);
    const q = e.target.closest('[data-q]')?.dataset.q;
    if (q === 'plan') return go('plan');
    if (q === 'near') { setExplore({ seg: 'pandals', sort: 'near', region: 'all', area: 'all', mode: 'list' }); go('explore'); if (!S.me) getFix().then(() => rerender()).catch(() => toast(t('loc.fail'))); return; }
    if (q === 'famous') { setExplore({ seg: 'pandals', sort: 'popular', region: 'all', area: 'all', mode: 'list' }); return go('explore'); }
    if (q === 'food') { setExplore({ seg: 'food', mode: 'list' }); return go('explore'); }
    if (q === 'park') { setExplore({ seg: 'parking', mode: 'list' }); return go('explore'); }
    if (q === 'photos') return go('moments');
    if (q === 'introClose') { store.set('introDone', true); return render(); }
    const place = e.target.closest('[data-place]')?.dataset.place; if (place) return openPlace(place);
    const hr = e.target.closest('[data-hr]')?.dataset.hr; if (hr) { setExplore({ seg: 'pandals', region: hr, area: 'all', mode: 'list' }); return go('explore'); }
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
  if (kind === 'zone') { setExplore({ seg: 'pandals', ...selectArea(id), mode: 'list' }); return go('explore'); }
  openPlace(id);
}

registerView('home', { render });
