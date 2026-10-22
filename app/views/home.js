/* Home: a simple start screen. "What would you like to do?" tasks, areas to pick, and ready-made routes. */
import { hav, fmtCount, searchEntries } from '../core.js';
import { S, G, idx, t, store, community, ll, nm, zn, zs, dn, zoneOf, esc, dist, greetDay, btn, icon, bnDigits, loc, plain, todayKey, savePrefs,
} from '../state.js';
import { $, go, rerender, toast, getFix, registerView } from '../ui.js';
import { openPlace } from '../sheets.js';
import { showTrail, openDayPlan, openSharedPlan, todayCardHtml, todayPlanIndex } from './plan.js';
import { setExplore } from './explore.js';
import { selectArea, rname } from '../filters.js';
import { radioCard, watchCard } from '../radioCard.js';
import { liveHtml } from '../livecount.js';
import { photosOn, pandalPhoto, dishPhoto, areaPhoto, tilePhoto, photoBg } from '../photos.js';
import { showAllReels } from '../reels.js';
import { deviceId } from '../growth.js';
import { track } from '../analytics.js';

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
/* The banner: greeting, the puja dates, and the promise with its "Plan my pujo" button. */
function heroHtml() {
  const SLIDES = slides();
  const today = greetDay();
  const shashthi = new Date(idx.day.shashthi.date + 'T00:00:00'), now = new Date(); now.setHours(0, 0, 0, 0);
  const diff = Math.round((shashthi - now) / 864e5);
  const over = pujoOver() && community.enabled;   // after Dashami the banner points at next year's reminder
  const when = today ? t('h.todayIs', { day: esc(dn(today)) }) : diff > 0 ? t('h.countdown', { n: bnDigits(diff) }) : over ? t('rm.when') : t('h.planning');
  return `<div class="hero slides" role="group" aria-roledescription="carousel" aria-label="${t('h.heroAlt', { place: '' })}">
    ${SLIDES.map((x, k) => `<button type="button" class="slide ${k === slide ? 'on' : ''}" data-slide="${k}" data-place="${x.pandal}" aria-label="${esc(nm(idx.pandal[x.pandal]))}">
      <img ${k === slide ? `src="${x.src}" fetchpriority="high"` : `data-src="${x.src}"`} alt="${t('h.heroAlt', { place: esc(nm(idx.pandal[x.pandal])) })}" style="object-position:${x.pos}" decoding="async"></button>`).join('')}
    <div class="hero-shade"></div>
    <div class="hero-copy">
      <div class="sharad-greet">${plain(t(today ? 'lingo.heroToday' : diff > 0 ? 'lingo.hero' : 'lingo.after'))}</div>
      <div class="sharad-sub">${t('h.greetSub')}</div>
      <div class="sharad-when"><span>${when}</span><span class="sep" aria-hidden="true">·</span><span>${span()}</span></div>
      <p class="hero-promise">${t('promise.title')}</p>
      <button type="button" class="hero-cta" data-q="${over ? 'remind' : 'myplan'}">${over ? t('rm.cta') : t('promise.cta')}</button>
    </div>
    <div class="hero-meta"><span class="hero-place"><span id="slidePlace">${esc(nm(idx.pandal[SLIDES[slide].pandal]))}</span></span></div>
    <div class="dots" aria-hidden="true">${SLIDES.map((_, k) => `<i class="${k === slide ? 'on' : ''}"></i>`).join('')}</div>
  </div>`;
}

/* Only the slide on screen loads with the page; each next one loads while the current one shows. Stacked slides all
 * count as "in view", so loading="lazy" fetched all five (about 1 MB) on the first visit. */
function warm(hero, k) {
  const img = hero?.querySelectorAll('.slide img')[k];
  if (img && !img.getAttribute('src') && img.dataset.src) img.src = img.dataset.src;
}
function startSlides(el) {
  const SLIDES = slides();
  clearInterval(slideTimer);
  if (SLIDES.length > 1) setTimeout(() => warm($('.hero.slides', el), (slide + 1) % SLIDES.length), 2500);
  if (SLIDES.length < 2 || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  slideTimer = setInterval(() => {
    if (S.view !== 'home' || document.hidden) return;
    const hero = $('.hero.slides', el); if (!hero) return;
    slide = (slide + 1) % SLIDES.length;
    warm(hero, slide); warm(hero, (slide + 1) % SLIDES.length);
    hero.querySelectorAll('.slide').forEach((b, k) => b.classList.toggle('on', k === slide));
    hero.querySelectorAll('.dots i').forEach((d, k) => d.classList.toggle('on', k === slide));
    const x = SLIDES[slide];
    $('#slidePlace', hero).textContent = nm(idx.pandal[x.pandal]);
  }, 5500);
}

// Four jobs, one tap each. Routes have the card above and their own tab; parking sits in Explore and on every pandal.
const TASKS = [
  ['near', 'locate'], ['famous', 'star'],
  ['food', 'food'], ['photos', 'camera'],
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
  return '';  // the shortcuts are plain icon tiles; photos are kept for areas, days and trails
  if (!photosOn()) return '';
  // Small copies of the banner photos (480 px): the full ones are for the banner only
  return ({ near: 'img/hero-3-sm.jpg', plan: pandalPhoto('tala_prattoy'), famous: 'img/hero-1-sm.jpg', food: dishPhoto(['Kathi roll', 'Biryani', 'Egg roll']),
    park: tilePhoto('parking'), photos: 'img/hero-2-sm.jpg' })[k] || '';
}
const regionImg = (r) => areaPhoto(r.zone_ids, r.id);

/* Under the banner (which carries the promise and "Plan my pujo"): search, since most people arrive looking for one
 * pandal, and the facts behind the promise in one line. */
/* After Dashami: "See you at Pujo 2027" with a WhatsApp reminder sign-up. It saves to the same consented contact list
 * as My Pujo (save_profile: only for pujo updates, removable there), so there's one list and one way out. */
const pujoOver = () => !!idx.day.dashami && todayKey() > idx.day.dashami.date;
const digits10 = (v) => { let d = String(v || '').replace(/\D/g, ''); if (d.length > 10 && /^(91|0)/.test(d)) d = d.replace(/^(91|0)/, ''); return d.slice(0, 10); };
function remindHtml() {
  if (!pujoOver() || !community.enabled) return '';
  const on = S.prefs.contactOk && S.prefs.phone;
  return `<section class="today-card remind" id="remindCard">
    <div class="tc-k">${t('rm.k')}</div>
    <h2>${t('rm.title')}</h2>
    <p class="tc-areas">${t(on ? 'rm.on' : 'rm.sub')}</p>
    ${on ? '' : `<form id="remindForm" class="rm-form" novalidate>
      <input id="rmName" type="text" autocomplete="given-name" maxlength="40" placeholder="${t('rm.name')}" aria-label="${t('rm.name')}" value="${esc(S.prefs.name || '')}">
      <span class="phone-in"><span class="cc">+91</span><input id="rmPhone" type="tel" inputmode="numeric" autocomplete="tel-national"
        placeholder="9830012345" aria-label="${t('rm.phone')}"></span>
      <button type="submit" class="btn primary block tc-go">${t('rm.btn')}</button>
      <p class="fine">${t('pr.shareNote')}</p></form>`}
  </section>`;
}

function promiseHtml(withCard = '') {
  return `<div class="search" role="search">
      ${icon('search')}
      <input id="homeSearch" type="search" autocomplete="off" placeholder="${t('h.search')}" aria-label="${t('h.search')}">
      <ul class="results" id="homeResults" role="listbox"></ul>
    </div>
    ${withCard}
    <p class="promise">${t('promise.sub', { n: bnDigits(G.data.pandals.length) })}</p>`;
}


function render() {
  const el = $('#view-home');
  const st = community.enabled ? community.stats.byPlace : {};
  const busy = Object.values(st).filter((s) => s.last_hour > 0 || s.today > 0)
    .sort((a, b) => b.last_hour - a.last_hour || b.today - a.today).slice(0, 8)
    .map((s) => idx.pandal[s.place_id]).filter(Boolean);
  const popular = busy.length ? [] : ((community.enabled && community.stats.popular) || [])
    .filter((x) => idx.pandal[x.place_id]).slice(0, 8);

  // The radio card is built once and moved in, never re-rendered, so its player keeps playing.
  if (!$('#homeTop', el)) el.innerHTML = '<div id="homeTop"></div><div id="homeRest"></div><div id="radioSlot"></div><div id="homeFoot"></div>';
  const slot = $('#radioSlot', el), card = radioCard();
  if (card.parentNode !== slot) slot.appendChild(card);
  watchCard();
  startSlides(el);
  $('#homeTop', el).innerHTML = `
    ${heroHtml()}
    ${promiseHtml(todayCardHtml() || remindHtml())}
    ${liveHtml()}
    <section class="section first"><div class="section-head"><h2>${plain(t('h.whatToDo'))}</h2></div>
      <div class="tasks">${TASKS.map(([k, ic]) => { const img = taskImg(k); return `<button class="task ${img ? 'photo' : ''}" data-q="${k}">${photoBg(img)}
        ${img ? '' : `<span class="task-ic">${icon(ic)}</span>`}<span class="task-t">${t('task.' + k)}</span><span class="task-s">${t('task.' + k + 'Sub')}</span></button>`; }).join('')}</div>
    </section>
`;
  $('#homeRest', el).innerHTML = `
    <section class="section"><div class="section-head"><div><h2>${plain(t('h.pickArea'))}</h2><p class="sub">${t('h.pickAreaSub')}</p></div></div>
      <div class="regions">${G.data.regions.map((r) => {
        const n = r.zone_ids.reduce((c, id) => c + (idx.zone[id]?.pandal_ids.length || 0), 0);
        const areas = r.zone_ids.map((id) => idx.zone[id]).filter(Boolean).map(zs).join(' · ');
        const img = regionImg(r);
        return `<button class="region ${img ? 'photo' : ''}" data-hr="${r.id}" style="--zc:${r.color}">${photoBg(img)}<span class="region-n">${esc(rname(r))}</span><span class="region-c">${t('h.pandalsN', { n })}</span><span class="region-a">${esc(areas)}</span></button>`;
      }).join('')}</div>
    </section>

    ${busy.length ? `<section class="section"><div class="section-head"><div><h2>${plain(t('h.trending'))}</h2><p class="sub">${t('h.trendingSub')}</p></div></div>
      <div class="hscroll">${busy.map((p) => { const s = st[p.id]; return miniPandal(p, s.last_hour
        ? `<span class="pill live"><span class="dot"></span>${t('c.liveN', { n: fmtCount(s.last_hour) })}</span>`
        : `<span class="pill">${icon('people', 'sm')} ${t('c.todayN', { n: fmtCount(s.today) })}</span>`); }).join('')}</div></section>` : ''}
    ${popular.length ? `<section class="section"><div class="section-head"><div><h2>${plain(t('h.popular'))}</h2><p class="sub">${t('h.popularSub')}</p></div></div>
      <div class="hscroll">${popular.map((x) => miniPandal(idx.pandal[x.place_id],
        `<span class="pill">${icon('people', 'sm')} ${t('c.lookedN', { n: fmtCount(x.people_7d) })}</span>`)).join('')}</div></section>` : ''}

`;
  $('#homeFoot', el).innerHTML = `
    <section class="section"><div class="section-head"><div><h2>${plain(t('kn.title'))}</h2><p class="sub">${t('kn.sub')}</p></div><a class="link-btn" href="durga-puja/">${t('h.seeAll')}</a></div>
      <div class="learn">${LEARN.map(([path, key, ic]) => `<a class="learn-card" href="${path}"><span aria-hidden="true">${icon(ic)}</span><b>${t('kn.' + key)}</b></a>`).join('')}</div></section>
    <footer class="home-foot"><div class="wm">Pujo Parikrama<span lang="bn">পুজো পরিক্রমা</span></div>
      <p class="fine" style="margin:10px 0 0">${t('p.disclaimer')} · <a href="privacy.html">${t('del.policy')}</a></p></footer>
`;

  wire(el);
}

/* "Know your pujo": links to the guide's articles (static pages, also what search engines index). */
const LEARN = [
  ['durga-puja/rituals/', 'rituals', 'diya'], ['durga-puja/rituals/pushpanjali-mantra/', 'anjali', 'flower'], ['durga-puja/what-is-durga-puja/', 'meaning', 'trident'],
  ['durga-puja/history/', 'history', 'scroll'], ['durga-puja/at-home/', 'home', 'home'], ['navratri/', 'navratri', 'sparkle'],
  ['durga-puja/food-and-bhog/', 'bhog', 'food'], ['durga-puja/bijoya-dashami-wishes/', 'wishes', 'letter'],
  ['durga-puja/pujo-pass/', 'pass', 'star'],
];

function wire(el) {
  el.onsubmit = async (e) => {
    if (e.target.id !== 'remindForm') return;
    e.preventDefault();
    const phone = digits10($('#rmPhone', el).value), name = $('#rmName', el).value.trim().slice(0, 40);
    if (!/^[6-9]\d{9}$/.test(phone)) { $('#rmPhone', el).focus(); return toast(t('pr.badPhone')); }
    const b = e.target.querySelector('button'); b.disabled = true;
    try {
      const r = await community.saveProfile(name, phone, true, { lang: S.prefs.lang, src: store.get('firstSrc', S.src || 'direct'), device: deviceId() });
      if (r.status !== 'ok') { b.disabled = false; return toast(t('pr.badPhone')); }
      Object.assign(S.prefs, { name, phone, contactOk: true }); savePrefs();
      track('remind', { d: '2027' });
      toast(t('rm.done')); rerender();
    } catch { b.disabled = false; toast(t('rm.fail')); }
  };
  el.onclick = (e) => {
    if (e.target.closest('.radio-card')) return;
    const dp = e.target.closest('[data-dayplan]')?.dataset.dayplan; if (dp) return openDayPlan(+dp);
    const q = e.target.closest('[data-q]')?.dataset.q;
    if (q === 'plan') return go('plan');
    if (q === 'remind') { const c = $('#remindCard', el); c?.scrollIntoView({ behavior: 'smooth', block: 'center' }); setTimeout(() => $('#rmPhone', el)?.focus({ preventScroll: true }), 450); return; }
    if (q === 'ownplan') return openSharedPlan(null);   // the route builder from its first step
    if (q === 'reels') return showAllReels(go);
    if (q === 'myplan') {   // today's ready route in one tap; the Routes tab when there isn't one
      const i = todayPlanIndex();
      return i >= 0 ? openDayPlan(i) : openSharedPlan(null);
    }
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
    }).join('') || (input.value.trim().length >= 2 ? `<li class="muted">${t('h.noResults')} <button type="button" class="link-btn" data-suggest data-name="${esc(input.value.trim())}">${t('sg.short')}</button></li>` : '');
  };
}
function pickResult(kind, id) {
  if (kind === 'zone') { setExplore({ seg: 'pandals', ...selectArea(id), mode: 'list' }); return go('explore'); }
  openPlace(id);
}

registerView('home', { render });
