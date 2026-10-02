/* DOM plumbing: query helpers, router, toast, bottom sheet, map factory. */
import { S, t, store } from './state.js';
import { CONFIG } from './config.js';

export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => [...r.querySelectorAll(s)];

/* ---------------- router ---------------- */
const views = {};
export const VIEWS = ['home', 'explore', 'plan', 'moments', 'me'];
export function registerView(name, { render, onShow } = {}) { views[name] = { render, onShow }; }
export function go(view, { keepScroll = false } = {}) {
  if (!VIEWS.includes(view)) view = 'home';
  S.view = view;
  $$('.tab').forEach((b) => { const on = b.dataset.view === view; b.classList.toggle('active', on); b.setAttribute('aria-current', on ? 'page' : 'false'); });
  $$('.view').forEach((v) => v.classList.toggle('active', v.id === 'view-' + view));
  $('#fabAdd').hidden = view !== 'moments';
  history.replaceState(null, '', '#' + view);
  if (!keepScroll) window.scrollTo(0, 0);
  views[view]?.render?.();
  views[view]?.onShow?.();
}
export const rerender = () => views[S.view]?.render?.();

/* ---------------- toast ---------------- */
let toastT;
export function toast(msg, ms = 2800) {
  const el = $('#toast'); el.textContent = msg; el.classList.add('show');
  clearTimeout(toastT); toastT = setTimeout(() => el.classList.remove('show'), ms);
}

/* ---------------- bottom sheet ---------------- */
let opener = null, onCloseCb = null;
export function setupSheet() {
  $('#sheetClose').onclick = closeSheet; $('#sheetBackdrop').onclick = closeSheet;
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSheet(); });
  let y0 = null; const sh = $('#sheet');
  sh.addEventListener('touchstart', (e) => { if (sh.scrollTop <= 0) y0 = e.touches[0].clientY; }, { passive: true });
  sh.addEventListener('touchend', (e) => { if (y0 != null && e.changedTouches[0].clientY - y0 > 90) closeSheet(); y0 = null; });
}
export function openSheet(html, onMount, onClose) {
  const s = $('#sheet');
  if (!s.classList.contains('open')) opener = document.activeElement;
  onCloseCb?.(); onCloseCb = onClose || null;
  $('#sheetBody').innerHTML = html; $('#sheetBackdrop').hidden = false;
  s.scrollTop = 0; s.setAttribute('aria-hidden', 'false');
  requestAnimationFrame(() => s.classList.add('open')); s.focus({ preventScroll: true });
  onMount?.($('#sheetBody'));
}
export function closeSheet() {
  const s = $('#sheet');
  if (!s.classList.contains('open')) return;
  s.classList.remove('open'); s.setAttribute('aria-hidden', 'true'); $('#sheetBackdrop').hidden = true;
  onCloseCb?.(); onCloseCb = null;
  $$('video', s).forEach((v) => v.pause());
  opener?.focus?.({ preventScroll: true }); opener = null;
}
export const sheetIsOpen = () => $('#sheet').classList.contains('open');

/* Make role=button elements keyboard-operable. */
export function setupA11y() {
  document.addEventListener('keydown', (e) => {
    const el = e.target;
    if ((e.key === 'Enter' || e.key === ' ') && el.getAttribute?.('role') === 'button' && el.tagName !== 'BUTTON') { e.preventDefault(); el.click(); }
  });
}

/* ---------------- maps ---------------- */
const isDark = () => document.documentElement.dataset.theme === 'dark' || (document.documentElement.dataset.theme !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches);
export function makeMap(el, { center = [22.555, 88.37], zoom = 12, animate = true } = {}) {
  if (!window.L) { el.innerHTML = `<p class="empty">${t('map.offline')}</p>`; return null; }
  const m = L.map(el, { zoomControl: false, attributionControl: true, zoomAnimation: animate, fadeAnimation: animate, markerZoomAnimation: animate }).setView(center, zoom);
  if (!S.prefs.lowData) {
    const c = CONFIG.map;
    L.tileLayer(isDark() ? c.dark : c.light, { maxZoom: c.maxZoom, subdomains: c.subdomains, detectRetina: true, attribution: c.attribution }).addTo(m);
  }
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
