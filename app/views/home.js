/* Home: a simple start screen. "What would you like to do?" tasks, areas to pick, and ready-made routes. */
import { hav, fmtCount, searchEntries } from '../core.js';
import { S, G, idx, t, store, community, ll, nm, zn, zs, dn, zoneOf, esc, dist, todayKey, btn, icon, bnDigits, loc,
} from '../state.js';
import { $, go, rerender, toast, getFix, registerView } from '../ui.js';
import { openPlace } from '../sheets.js';
import { showTrail, dayPlanHtml, openDayPlan } from './plan.js';
import { setExplore } from './explore.js';
import { selectArea, rname } from '../filters.js';
import { radioCard, watchCard, musicStripHtml, musicStripClick } from '../radioCard.js';
import { liveHtml } from '../livecount.js';
import { carCardHtml, carClick } from '../car.js';
import { photosOn, pandalPhoto, dishPhoto, areaPhoto, tilePhoto, photoBg } from '../photos.js';

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

/* Banner: a slow slideshow of real protimas (Wikimedia Commons; each slide credits its photographer).
 * Tapping a slide opens that pandal. Positions keep Ma's face in frame on a wide crop. */
const SLIDE_DATA = [
  { src: 'img/hero-1.jpg', pos: '50% 12%', pandal: 'bagbazar', author: 'Tarunsamanta', license: 'CC BY-SA 4.0', page: 'https://commons.wikimedia.org/wiki/File:Bagbazar_Srbojanin_Durga_Puja_2025_02.jpg' },
  { src: 'img/hero-2.jpg', pos: '50% 30%', pandal: 'kumartuli_sarbojanin', author: 'Tarunsamanta', license: 'CC BY-SA 4.0', page: 'https://commons.wikimedia.org/wiki/File:Kumartuli_Sarbojanin_Durgatsab_2025_01.jpg' },
  { src: 'img/hero-3.jpg', pos: '50% 32%', pandal: 'jagat_mukherjee', author: 'Tarunsamanta', license: 'CC BY-SA 4.0', page: 'https://commons.wikimedia.org/wiki/File:Jagat_Mukherjee_Park_Durga_Puja_2025_09.jpg' },
  { src: 'img/hero-4.jpg', pos: '50% 20%', pandal: 'college_square', author: 'Jonoikobangali', license: 'CC BY-SA 3.0', page: 'https://commons.wikimedia.org/wiki/File:Durga_College_Square_Arnab_Dutta_2011.jpg' },
  { src: 'img/hero-5.jpg', pos: '50% 28%', pandal: 'md_ali_park', author: 'Indrajit Das', license: 'CC BY-SA 3.0', page: 'https://commons.wikimedia.org/wiki/File:DurgaPuja2017_-_Durga_Idol_of_Mohammad_Ali_Park_01.jpg' },
];
const slides = () => SLIDE_DATA.filter((x) => idx.pandal[x.pandal]);
let slide = 0, slideTimer = null;

const span = () => { const o = { day: 'numeric' }, a = new Date(idx.day.shashthi.date + 'T00:00:00'), b = new Date(idx.day.dashami.date + 'T00:00:00');
  return `${a.toLocaleDateString(loc(), o)}–${b.toLocaleDateString(loc(), { day: 'numeric', month: 'short' })}`; };
/* The banner: greeting, the puja dates, and the one crowd tip that matters. */
function heroHtml() {
  const SLIDES = slides();
  const today = G.data.meta.days.find((d) => d.date === todayKey());
  const shashthi = new Date(idx.day.shashthi.date + 'T00:00:00'), now = new Date(); now.setHours(0, 0, 0, 0);
  const diff = Math.round((shashthi - now) / 864e5);
  const when = today ? t('h.todayIs', { day: esc(dn(today)) }) : diff > 0 ? t('h.countdown', { n: bnDigits(diff) }) : t('h.planning');
  return `<div class="hero slides" role="group" aria-roledescription="carousel" aria-label="${t('h.heroAlt', { place: '' })}">
    ${SLIDES.map((x, k) => `<button type="button" class="slide ${k === slide ? 'on' : ''}" data-slide="${k}" data-place="${x.pandal}" aria-label="${esc(nm(idx.pandal[x.pandal]))}">
      <img src="${x.src}" alt="${t('h.heroAlt', { place: esc(nm(idx.pandal[x.pandal])) })}" style="object-position:${x.pos}" ${k ? 'loading="lazy"' : 'fetchpriority="high"'} decoding="async"></button>`).join('')}
    <div class="hero-shade"></div>
    <div class="hero-copy">
      <div class="sharad-greet">${t(today ? 'lingo.heroToday' : diff > 0 ? 'lingo.hero' : 'lingo.after')}</div>
      <div class="sharad-sub">${t('h.greetSub')}</div>
      <div class="sharad-when"><span>${when}</span><span class="sep">·</span><span>${span()}</span></div>
    </div>
    <div class="hero-meta"><span class="hero-place">📍 <span id="slidePlace">${esc(nm(idx.pandal[SLIDES[slide].pandal]))}</span></span></div>
    <div class="dots" aria-hidden="true">${SLIDES.map((_, k) => `<i class="${k === slide ? 'on' : ''}"></i>`).join('')}</div>
  </div>`;
}

function startSlides(el) {
  const SLIDES = slides();
  clearInterval(slideTimer);
  if (SLIDES.length < 2 || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  slideTimer = setInterval(() => {
    if (S.view !== 'home' || document.hidden) return;
    const hero = $('.hero.slides', el); if (!hero) return;
    slide = (slide + 1) % SLIDES.length;
    hero.querySelectorAll('.slide').forEach((b, k) => b.classList.toggle('on', k === slide));
    hero.querySelectorAll('.dots i').forEach((d, k) => d.classList.toggle('on', k === slide));
    const x = SLIDES[slide];
    $('#slidePlace', hero).textContent = nm(idx.pandal[x.pandal]);
  }, 5500);
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

function taskImg(k) {
  if (!photosOn()) return '';
  return ({ near: 'img/hero-3.jpg', plan: pandalPhoto('tala_prattoy'), famous: 'img/hero-1.jpg', food: dishPhoto(['Kathi roll', 'Biryani', 'Egg roll']),
    park: tilePhoto('parking'), photos: 'img/hero-2.jpg' })[k] || '';
}
const regionImg = (r) => areaPhoto(r.zone_ids, r.id);
const trailImg = (it) => (photosOn() ? it.segments.flatMap((sg) => sg.stops || []).map((x) => pandalPhoto(x.pandal, 500)).find(Boolean) || '' : '');

// How to use the app, in order: each step opens that part of it.
const HOW = [['plan', '🗺️'], ['famous', '🛕'], ['go', '📍'], ['share', '📸']];

function render() {
  const el = $('#view-home');
  const st = community.enabled ? community.stats.byPlace : {};
  const busy = Object.values(st).filter((s) => s.last_hour > 0 || s.today > 0)
    .sort((a, b) => b.last_hour - a.last_hour || b.today - a.today).slice(0, 8)
    .map((s) => idx.pandal[s.place_id]).filter(Boolean);

  // The radio card is built once and moved in, never re-rendered, so its player keeps playing.
  if (!$('#homeTop', el)) el.innerHTML = '<div id="homeTop"></div><div id="radioSlot"></div><div id="homeRest"></div>';
  const slot = $('#radioSlot', el), card = radioCard();
  if (card.parentNode !== slot) slot.appendChild(card);
  watchCard();
  startSlides(el);
  $('#homeTop', el).innerHTML = `
    ${heroHtml()}
    ${musicStripHtml()}
    ${liveHtml()}
    <section class="how-wrap" aria-label="${t('h.introTitle')}">
      <p class="how-lingo">${t('how.lingo')}</p>
      <ol class="how">${HOW.map(([q, em], i) => `<li><button type="button" data-q="${q}"><span class="how-n">${i + 1}</span><span class="how-em" aria-hidden="true">${em}</span>
        <span class="how-tx"><b>${t('how.t' + (i + 1))}</b><span>${t('how.s' + (i + 1))}</span></span><span class="how-go" aria-hidden="true">›</span></button></li>`).join('')}</ol>
    </section>
    <section class="section first"><div class="section-head"><h2>${t('h.whatToDo')}</h2></div>
      <div class="tasks">${TASKS.map(([k, ic]) => { const img = taskImg(k); return `<button class="task ${img ? 'photo' : ''}" data-q="${k}">${photoBg(img)}
        ${img ? '' : `<span class="task-ic">${icon(ic)}</span>`}<span class="task-t">${t('task.' + k)}</span><span class="task-s">${t('task.' + k + 'Sub')}</span></button>`; }).join('')}</div>
    </section>

    <div id="homeCar">${carCardHtml()}</div>

    <div class="search" role="search">
      ${icon('search')}
      <input id="homeSearch" type="search" autocomplete="off" placeholder="${t('h.search')}" aria-label="${t('h.search')}">
      <ul class="results" id="homeResults" role="listbox"></ul>
    </div>`;
  $('#homeRest', el).innerHTML = `



    <section class="section"><div class="section-head"><div><h2>${t('h.pickArea')}</h2><p class="sub">${t('h.pickAreaSub')}</p></div></div>
      <div class="regions">${G.data.regions.map((r) => {
        const n = r.zone_ids.reduce((c, id) => c + (idx.zone[id]?.pandal_ids.length || 0), 0);
        const areas = r.zone_ids.map((id) => idx.zone[id]).filter(Boolean).map(zs).join(' · ');
        const img = regionImg(r);
        return `<button class="region ${img ? 'photo' : ''}" data-hr="${r.id}" style="--zc:${r.color}">${photoBg(img)}<span class="region-n">${esc(rname(r))}</span><span class="region-c">${t('h.pandalsN', { n })}</span><span class="region-a">${esc(areas)}</span></button>`;
      }).join('')}</div>
    </section>

    ${busy.length ? `<section class="section"><div class="section-head"><div><h2>${t('h.trending')}</h2><p class="sub">${t('h.trendingSub')}</p></div></div>
      <div class="hscroll">${busy.map((p) => { const s = st[p.id]; return miniPandal(p, s.last_hour
        ? `<span class="pill live"><span class="dot"></span>${t('c.liveN', { n: fmtCount(s.last_hour) })}</span>`
        : `<span class="pill">${icon('people', 'sm')} ${t('c.todayN', { n: fmtCount(s.today) })}</span>`); }).join('')}</div></section>` : ''}

    <section class="section"><div class="section-head"><div><h2>${t('dp.title')}</h2><p class="sub">${t('dp.sub')}</p></div></div>
      ${dayPlanHtml()}</section>

    <section class="section"><div class="section-head"><div><h2>${t('h.trails')}</h2><p class="sub">${t('h.trailsSub')}</p></div><button class="link-btn" data-q="plan">${t('h.seeAll')}</button></div>
      <div class="list">${G.data.itineraries.slice(0, 3).map((it) => `<div class="card trail ${trailImg(it) ? 'photo' : ''}" data-trail="${it.id}" ${btn()}>${photoBg(trailImg(it))}
        <h3>${esc((S.prefs.lang === 'bn' && it.name_bn) || it.name)}</h3>
        <div class="row"><span>${t('it.pandals', { n: it.pandal_count })}</span><span>${it.totals.walk_km} km</span><span>${dn(idx.day[it.day])} · ${it.start_time}</span></div></div>`).join('')}</div></section>
    <p class="fine center" style="margin:24px 16px 0">${t('p.disclaimer')}</p>
`;

  wire(el);
}

function wire(el) {
  el.onclick = (e) => {
    if (e.target.closest('.radio-card')) return;
    if (musicStripClick(e)) return;
    if (carClick(e, () => { const c = $('#homeCar', el); if (c) c.innerHTML = carCardHtml(); })) return;
    const dp = e.target.closest('[data-dayplan]')?.dataset.dayplan; if (dp) return openDayPlan(+dp);
    const q = e.target.closest('[data-q]')?.dataset.q;
    if (q === 'plan') return go('plan');
    if (q === 'near') { setExplore({ seg: 'pandals', sort: 'near', region: 'all', area: 'all', mode: 'list' }); go('explore'); if (!S.me) getFix().then(() => rerender()).catch(() => toast(t('loc.fail'))); return; }
    if (q === 'famous') { setExplore({ seg: 'pandals', sort: 'popular', region: 'all', area: 'all', mode: 'list' }); return go('explore'); }
    if (q === 'food') { setExplore({ seg: 'food', mode: 'list' }); return go('explore'); }
    if (q === 'park') { setExplore({ seg: 'parking', mode: 'list' }); return go('explore'); }
    if (q === 'photos') return go('moments');
    if (q === 'go') { setExplore({ seg: 'pandals', sort: 'near', region: 'all', area: 'all', mode: 'list' }); go('explore'); if (!S.me) getFix().then(() => rerender()).catch(() => {}); return; }
    if (q === 'share') return go('me');
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
