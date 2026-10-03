/* Pujo Parikrama 2026: entry point. Loads the guide data, wires up the shell and the
 * community sync, then hands off to the views in ./views. */
import { decodePlan } from './core.js';
import { S, G, idx, t, store, community, loadGuide, dn, todayKey, savePrefs, bnDigits } from './state.js';
import { $, $$, go, rerender, toast, setupSheet, setupA11y, VIEWS, sheetIsOpen, initVectorTiles, refreshBaseLayers } from './ui.js';
import './views/home.js';
import './views/explore.js';
import { openSharedPlan, showTrail } from './views/plan.js';
import { setupMoments } from './views/moments.js';
import './views/me.js';
import { CONFIG } from './config.js';
import { captureSource, trackOpen } from './growth.js';
import { openPlace } from './sheets.js';

async function boot() {
  let g;
  try { g = await (await fetch('data/guide.json', { cache: 'no-cache' })).json(); }
  catch { $('#main').innerHTML = `<p class="empty">${t('load.fail')}</p>`; return; }
  loadGuide(g);

  const prev = store.get('dataVersion', null);
  if (prev && prev !== g.meta.version) setTimeout(() => toast(t('data.updated')), 900);
  store.set('dataVersion', g.meta.version);
  const todayDay = g.meta.days.find((d) => d.date === todayKey());
  S.day = todayDay ? todayDay.id : store.get('day', null) || 'saptami';
  const lf = store.get('lastFix', null);
  if (lf && Date.now() - lf.t < 30 * 60e3) S.me = [lf[0], lf[1]];

  captureSource();
  setupHeader(); setupSheet(); setupA11y(); setupMoments();
  $$('.tab').forEach((b) => (b.onclick = () => go(b.dataset.view)));
  applyStatic();

  const hash = location.hash.slice(1);
  if (hash.startsWith('plan=')) openSharedPlan(decodePlan(hash.slice(5)));
  else if (hash.startsWith('trail=') && g.itineraries.some((i) => i.id === hash.slice(6))) { go('plan'); showTrail(hash.slice(6)); toast(t('share.loaded')); }
  else if (hash.startsWith('p=') && (idx.pandal[hash.slice(2)] || idx.food[hash.slice(2)] || idx.parking[hash.slice(2)])) { go('home'); openPlace(hash.slice(2)); }
  else go(VIEWS.includes(hash) ? hash : hash === 'fit' ? 'me' : hash === 'food' || hash === 'park' ? 'explore' : 'home');

  setupCommunity();
  trackOpen();
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
  $('#daySelect').onchange = (e) => { S.day = e.target.value; store.set('day', S.day); rerender(); };
  $('#langBtn').onclick = () => { S.prefs.lang = S.prefs.lang === 'bn' ? 'en' : 'bn'; savePrefs(); applyStatic(); rerender(); refreshBaseLayers(); };
}

/* Static text in index.html carries data-i18n keys; the views re-render themselves. */
function applyStatic() {
  document.documentElement.lang = S.prefs.lang;
  $$('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n); });
  $('#langBtn').textContent = t('lang.toggle');
  $('#langBtn').setAttribute('aria-label', t('lang.aria'));
  $('#sheetClose').setAttribute('aria-label', t('sheet.close'));
  $('#fabAdd').setAttribute('aria-label', t('m.add'));
  $('#locateBtn').setAttribute('aria-label', t('loc.me'));
  const sel = $('#daySelect');
  sel.innerHTML = G.data.meta.days.map((d) => `<option value="${d.id}">${dn(d)}</option>`).join('');
  sel.value = S.day;
  const now = new Date(); now.setHours(0, 0, 0, 0);
  const shashthi = new Date(idx.day.shashthi.date + 'T00:00:00'), dashami = new Date(idx.day.dashami.date + 'T00:00:00');
  const todayDay = G.data.meta.days.find((d) => d.date === todayKey()), diff = Math.round((shashthi - now) / 864e5);
  $('#countdown').textContent = todayDay ? t('count.today', { day: dn(todayDay) }) : now > dashami ? t('count.after')
    : diff === 1 ? t('count.day') : t('count.days', { n: bnDigits(diff) });
}

boot();
