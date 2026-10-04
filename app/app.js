/* Pujo Parikrama 2026: entry point. Loads the guide data, wires up the shell and the
 * community sync, then hands off to the views in ./views. */
import { decodePlan, parseSteps } from './core.js';
import { S, G, idx, t, store, community, loadGuide, dn, todayKey, savePrefs, bnDigits, loc } from './state.js';
import { dayRec, saveHistory } from './actions.js';
import { $, $$, go, rerender, toast, setupSheet, setupA11y, VIEWS, sheetIsOpen, initVectorTiles, refreshBaseLayers } from './ui.js';
import './views/home.js';
import './views/explore.js';
import { openSharedPlan, showTrail } from './views/plan.js';
import { setupMoments } from './views/moments.js';
import './views/me.js';
import { CONFIG } from './config.js';
import { captureSource, trackOpen } from './growth.js';
import { openPlace } from './sheets.js';
import { initMini } from './radioCard.js';
import { startAnalytics, track } from './analytics.js';
import { startLiveCount, counts, onCounts } from './livecount.js';
import { initCelebrations } from './celebrate.js';

function syncSteps(s) {
  const r = parseSteps(s, todayKey());
  history.replaceState(null, '', location.pathname + location.search + '#me');
  go('me');
  if (!r) return toast(t('hs.bad'));
  dayRec(r.date).health = r.n; saveHistory(); rerender();
  toast(t('hs.synced', { n: r.n.toLocaleString(loc()) }), 3500);
}

async function boot() {
  let g;
  try { g = await (await fetch('data/guide.json', { cache: 'no-cache' })).json(); }
  catch { $('#main').innerHTML = `<p class="empty">${t('load.fail')}</p>`; return; }
  loadGuide(g);

  const prev = store.get('dataVersion', null);
  if (prev && prev !== g.meta.version) setTimeout(() => toast(t('data.updated')), 900);
  store.set('dataVersion', g.meta.version);
  const todayDay = g.meta.days.find((d) => d.date === todayKey());
  // The puja day drives crowd estimates. It follows the calendar; My route and the Map's crowd panel can look at another day.
  const ahead = g.meta.days.find((d) => d.date > todayKey() && d.id !== 'mahalaya');
  // Not remembered between visits: a day picked while planning (e.g. the 6-day plan's Panchami) shouldn't become everyone's default.
  S.day = todayDay && todayDay.id !== 'mahalaya' ? todayDay.id : ahead ? 'saptami' : 'dashami';
  const lf = store.get('lastFix', null);
  if (lf && Date.now() - lf.t < 30 * 60e3) S.me = [lf[0], lf[1]];

  captureSource();
  setupHeader(); setupSheet(); setupA11y(); setupMoments();
  $$('.tab').forEach((b) => (b.onclick = () => go(b.dataset.view)));
  applyStatic();

  const hash = location.hash.slice(1);
  if (hash.startsWith('steps=')) syncSteps(hash.slice(6));
  else if (hash.startsWith('plan=')) openSharedPlan(decodePlan(hash.slice(5)));
  else if (hash.startsWith('trail=') && g.itineraries.some((i) => i.id === hash.slice(6))) { go('plan'); showTrail(hash.slice(6)); toast(t('share.loaded')); }
  else if (hash.startsWith('p=') && (idx.pandal[hash.slice(2)] || idx.food[hash.slice(2)] || idx.parking[hash.slice(2)])) { go('home'); openPlace(hash.slice(2)); }
  else go(VIEWS.includes(hash) ? hash : hash === 'fit' ? 'me' : hash === 'food' || hash === 'park' ? 'explore' : 'home');

  setupCommunity();
  trackOpen();
  startAnalytics();
  initCelebrations();
  startLiveCount();
  onCounts(() => applyStatic(false));
  initMini();
  if (!S.prefs.lowData) initVectorTiles();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
  addEventListener('offline', () => toast(t('net.off')));
  addEventListener('online', () => { toast(t('net.on')); community.sync(); });
  if (!navigator.onLine) setTimeout(() => toast(t('net.off')), 600);
}

function setupCommunity() {
  if (!community.enabled) return;
  let renderT = null;
  // Re-render on fresh counts, but never under an open sheet (it would steal focus).
  community.on((type) => {
    if (type !== 'stats') return;
    clearTimeout(renderT);
    renderT = setTimeout(() => { if (!sheetIsOpen() && ['home', 'explore'].includes(S.view)) rerender(); }, 250);
  });
  community.on((type, d) => { if (type === 'flushed') toast(t('m.flushed', { n: d })); });
  community.sync();
  setInterval(() => { if (document.visibilityState === 'visible' && navigator.onLine) community.refreshStats().catch(() => {}); }, CONFIG.community.statsRefreshSec * 1000);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') community.sync(); });
}

function setupHeader() {
  $('#langSelect').onchange = (e) => { S.prefs.lang = e.target.value; track('lang', { d: e.target.value }); savePrefs(); applyStatic(); rerender(); refreshBaseLayers(); };
}

/* Static text in index.html carries data-i18n keys; the views re-render themselves. */
function applyStatic(full = true) {
  if (!full) return startTicker(tickerLines(), true);
  document.documentElement.lang = S.prefs.lang;
  $$('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n); });
  $('#langSelect').value = S.prefs.lang;
  $('#langSelect').setAttribute('aria-label', t('lang.aria'));
  $('#sheetClose').setAttribute('aria-label', t('sheet.close'));
  $('#fabAdd').setAttribute('aria-label', t('m.add'));
  $('#locateBtn').setAttribute('aria-label', t('loc.me'));
  const now = new Date(); now.setHours(0, 0, 0, 0);
  const shashthi = new Date(idx.day.shashthi.date + 'T00:00:00'), dashami = new Date(idx.day.dashami.date + 'T00:00:00');
  const todayDay = G.data.meta.days.find((d) => d.date === todayKey()), diff = Math.round((shashthi - now) / 864e5);
  // The big line is the day's greeting in Bengali: শুভ শারদীয়া before the pujo, শুভ সপ্তমী on the day, শুভ বিজয়া after.
  $('#greet').textContent = todayDay ? (todayDay.id === 'dashami' ? 'শুভ বিজয়া' : `শুভ ${todayDay.name_bn}`) : now > dashami ? 'শুভ বিজয়া' : 'শুভ শারদীয়া';
  // The line under the name rotates through what people say around the pujo, led by the countdown.
  const lead = todayDay ? t('lingo.today', { day: dn(todayDay) }) : now > dashami ? t('lingo.after')
    : t('lingo.count', { n: bnDigits(Math.max(1, diff)) });
  leadLine = lead;
  startTicker(tickerLines());
}

/* The header ticker: the countdown or today's greeting, real usage numbers when they're worth showing, and pujo lingo. */
let leadLine = '';
function tickerLines() {
  const c = counts(), n = (v) => Number(v).toLocaleString(loc());
  return [leadLine,
    c.today >= 50 ? t('lv.today', { n: n(c.today) }) : null,
    t('lingo.1'), t('lingo.2'),
    c.people >= 500 ? t('lv.totalTick', { n: n(Math.floor(c.people / 100) * 100) }) : null,
    t('lingo.3'), t('lingo.4'), t('lingo.5'), t('lingo.6')].filter(Boolean);
}

let tickTimer = null;
let tickLines = [];
function startTicker(lines, keep = false) {
  const el = $('#countdown');
  tickLines = lines;
  if (keep && tickTimer) return; // the running ticker picks up the new lines on its next turn
  let i = 0;
  el.textContent = lines[0];
  clearInterval(tickTimer);
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  tickTimer = setInterval(() => {
    i = (i + 1) % tickLines.length;
    el.classList.add('out');
    setTimeout(() => { el.textContent = tickLines[i]; el.classList.remove('out'); }, 260);
  }, 3800);
}

boot();
