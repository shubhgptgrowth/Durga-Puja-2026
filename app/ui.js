/* DOM plumbing: query helpers, router, toast, bottom sheet, map factory. */
import { S, t, store } from './state.js';
import { CONFIG } from './config.js';

export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => [...r.querySelectorAll(s)];

/* ---------------- router ---------------- */
const views = {};
export const VIEWS = ['home', 'explore', 'plan', 'moments', 'me'];
export function registerView(name, { render, onShow } = {}) { views[name] = { render, onShow }; }
/* Back button: each tab change and each opened page (sheet) is a history entry, so Back goes to the previous
 * tab or closes the page instead of leaving the site. */
let booted = false, sheetEntry = false, skipPop = 0;
export function go(view, { keepScroll = false, push = true } = {}) {
  if (!VIEWS.includes(view)) view = 'home';
  const changed = view !== S.view || !booted;
  // A page (sheet) open while switching tab: reuse its history entry rather than go back and forward at once.
  let reuse = false;
  if (sheetIsOpen()) { reuse = sheetEntry; sheetEntry = false; closeSheet(true); }
  S.view = view;
  $$('.tab').forEach((b) => { const on = b.dataset.view === view; b.classList.toggle('active', on); b.setAttribute('aria-current', on ? 'page' : 'false'); });
  $$('.view').forEach((v) => v.classList.toggle('active', v.id === 'view-' + view));
  $('#fabAdd').hidden = view !== 'moments';
  if (booted && push && changed && !reuse) history.pushState({ view }, '', '#' + view);
  else history.replaceState({ view }, '', '#' + view);
  booted = true;
  if (!keepScroll) window.scrollTo(0, 0);
  views[view]?.render?.();
  views[view]?.onShow?.();
  dispatchEvent(new CustomEvent('viewchange', { detail: view }));
}
export const rerender = () => views[S.view]?.render?.();

/* ---------------- toast ---------------- */
let toastT;
export function toast(msg, ms = 2800) {
  const el = $('#toast'); el.textContent = msg; el.classList.add('show');
  clearTimeout(toastT); toastT = setTimeout(() => el.classList.remove('show'), ms);
}

/* ---------------- bottom sheet ---------------- */
let opener = null, onCloseCb = null, openTok = 0;
export function setupSheet() {
  $('#sheetClose').onclick = closeSheet; $('#sheetBackdrop').onclick = closeSheet;
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSheet(); });
  let y0 = null; const sh = $('#sheet');
  sh.addEventListener('touchstart', (e) => { if (sh.scrollTop <= 0) y0 = e.touches[0].clientY; }, { passive: true });
  sh.addEventListener('touchend', (e) => { if (y0 != null && e.changedTouches[0].clientY - y0 > 90) closeSheet(); y0 = null; });
}
export function openSheet(html, onMount, onClose) {
  const s = $('#sheet');
  if (!sheetIsOpen()) opener = document.activeElement;
  onCloseCb?.(); onCloseCb = onClose || null;
  $('#sheetBody').innerHTML = html; $('#sheetBackdrop').hidden = false;
  s.scrollTop = 0; s.setAttribute('aria-hidden', 'false');
  const tok = ++openTok; requestAnimationFrame(() => { if (tok === openTok) s.classList.add('open'); }); s.focus({ preventScroll: true });
  if (!sheetEntry && booted) { history.pushState({ view: S.view, sheet: true }, '', location.hash); sheetEntry = true; }
  onMount?.($('#sheetBody'));
}
export function closeSheet(fromBack = false) {
  const s = $('#sheet');
  if (!sheetIsOpen()) return;
  if (sheetEntry) { sheetEntry = false; if (fromBack !== true) { skipPop++; history.back(); } } // drop the page's history entry
  openTok++; s.classList.remove('open'); s.setAttribute('aria-hidden', 'true'); $('#sheetBackdrop').hidden = true;
  onCloseCb?.(); onCloseCb = null;
  $$('video', s).forEach((v) => v.pause());
  opener?.focus?.({ preventScroll: true }); opener = null;
}
export const sheetIsOpen = () => $('#sheet').getAttribute('aria-hidden') === 'false';

addEventListener('popstate', (e) => {
  if (skipPop) { skipPop--; return; }
  if (sheetIsOpen()) return closeSheet(true);
  const view = e.state?.view || location.hash.slice(1);
  if (VIEWS.includes(view) && view !== S.view) go(view, { push: false });
});

/* Make role=button elements keyboard-operable. */
export function setupA11y() {
  document.addEventListener('keydown', (e) => {
    const el = e.target;
    if ((e.key === 'Enter' || e.key === ' ') && el.getAttribute?.('role') === 'button' && el.tagName !== 'BUTTON') { e.preventDefault(); el.click(); }
  });
}

/* ---------------- maps ---------------- */
const isDark = () => document.documentElement.dataset.theme === 'dark' || (document.documentElement.dataset.theme !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches);
const liveMaps = new Set();
let vector = null;   // {url, maxzoom, build} once the self-hosted vector tiles are confirmed readable

/** Check the vector tile manifest and that the file answers range requests. Falls back to raster quietly. */
export async function initVectorTiles() {
  const mf = CONFIG.map.vectorManifest;
  if (!mf || !window.protomapsL) return false;
  try {
    const m = await (await fetch(mf, { cache: 'no-cache' })).json();
    if (!m.file) return false;
    const url = new URL(m.file, new URL(mf, location.href)).href;
    const head = await fetch(url, { headers: { Range: 'bytes=0-6' } });
    const magic = new TextDecoder().decode((await head.arrayBuffer()).slice(0, 7));
    if (!(head.status === 206 || head.status === 200) || magic !== 'PMTiles') return false;
    vector = { url, maxzoom: m.maxzoom || 15, build: m.build };
    refreshBaseLayers();
    return true;
  } catch { return false; }
}
export const mapEngine = () => (vector ? 'vector' : 'raster');

function baseLayer() {
  const c = CONFIG.map;
  if (vector) {
    return protomapsL.leafletLayer({ url: vector.url, flavor: isDark() ? 'dark' : 'light', lang: S.prefs.lang,
      maxDataZoom: vector.maxzoom, maxZoom: c.maxZoom,
      attribution: '<a href="https://protomaps.com">Protomaps</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' });
  }
  return L.tileLayer(isDark() ? c.dark : c.light, { maxZoom: c.maxZoom, subdomains: c.subdomains, detectRetina: true, attribution: c.attribution });
}

/** Swap every live map's base layer (after the vector tiles load, or the language or theme changes). */
export function refreshBaseLayers() {
  for (const m of liveMaps) {
    if (!m._container?.isConnected) { liveMaps.delete(m); continue; }
    if (S.prefs.lowData) continue;
    m._base?.remove(); m._base = baseLayer().addTo(m); m._base.bringToBack?.();
  }
}
matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', refreshBaseLayers);

export function makeMap(el, { center = [22.555, 88.37], zoom = 12, animate = true } = {}) {
  if (!window.L) { el.innerHTML = `<p class="empty">${t('map.offline')}</p>`; return null; }
  const m = L.map(el, { zoomControl: false, attributionControl: true, zoomAnimation: animate, fadeAnimation: animate, markerZoomAnimation: animate }).setView(center, zoom);
  if (!S.prefs.lowData) m._base = baseLayer().addTo(m);
  liveMaps.add(m);
  m.on('unload', () => liveMaps.delete(m));
  return m;
}
export function pinIcon(color, size, label = '', cls = '') {
  return L.divIcon({ className: '', iconSize: [size, size], iconAnchor: [size / 2, size / 2],
    html: `<div class="pin ${cls}" style="width:${size}px;height:${size}px;background:${color}">${label}</div>` });
}

/* ---------------- location ---------------- */
/** One fresh, high-accuracy fix. Resolves {lat, lng, accuracy, t}, or rejects with {code}. */
export function getFix({ timeout = 12000, maximumAge = 15000 } = {}) {
  return new Promise((res, rej) => {
    if (!navigator.geolocation) return rej({ code: 'na' });
    navigator.geolocation.getCurrentPosition(
      (p) => { S.me = [p.coords.latitude, p.coords.longitude]; store.set('lastFix', { ...S.me, t: Date.now() });
        res({ lat: p.coords.latitude, lng: p.coords.longitude, accuracy: p.coords.accuracy, t: p.timestamp || Date.now() }); },
      (e) => rej({ code: e.code === 1 ? 'denied' : 'unavailable' }),
      { enableHighAccuracy: true, timeout, maximumAge });
  });
}
