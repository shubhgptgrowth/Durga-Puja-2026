/* DOM plumbing: query helpers, router, toast, bottom sheet, map factory. */
import { S, t, store } from './state.js';

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
