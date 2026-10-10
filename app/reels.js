/* Pujo Reels: the videos we post and repost on Instagram (plus hand-picked Facebook/YouTube ones), shown on Home and in
 * Moments. Built at deploy by scripts/reels_feed.py into data/reels.json. Videos are embedded, never downloaded: the
 * player is Instagram's, Facebook's or YouTube's own embed, loaded only when someone taps a reel. Each reel credits its
 * creator, links back to the post, and opens its pandal in the guide, so watching leads into planning a visit. */
import { S, idx, t, esc, nm } from './state.js';
import { embedUrl } from './core.js';
import { openSheet, toast } from './ui.js';
import { openPlace } from './sheets.js';
import { track } from './analytics.js';
import * as radio from './radio.js';

let reels = null, loading = null;
const onLoad = new Set();

/** Fetch the feed once. Calls `fn` when it arrives (only if there is something to show). */
export function loadReels(fn) {
  if (reels) return Promise.resolve(reels);
  if (fn) onLoad.add(fn);
  loading ||= fetch('data/reels.json').then((r) => (r.ok ? r.json() : { reels: [] }))
    .then((d) => {
      reels = (d.reels || []).filter((r) => embedUrl(r.url));
      if (reels.length) onLoad.forEach((f) => f());
      onLoad.clear();
      return reels;
    })
    .catch(() => { reels = []; return reels; });
  return loading;
}
export const reelList = () => reels || [];

const SRC = { ig: 'Instagram', fb: 'Facebook', yt: 'YouTube' };
function tileHtml(r, i) {
  const p = r.pandal && idx.pandal[r.pandal];
  const img = r.thumb && !S.prefs.lowData
    ? `<img src="${esc(r.thumb)}" alt="" loading="lazy" decoding="async" onerror="this.remove()">` : '';
  return `<button type="button" class="reel-tile ${img ? '' : 'no-img'}" data-reel="${i}" aria-label="${esc(r.title || t('rl.watch'))}">${img}
    <span class="reel-play" aria-hidden="true">▶</span>${r.sponsored ? `<span class="sponsored">${t('of.sponsored')}</span>` : ''}
    <span class="reel-tx"><b>${esc(r.title || (p ? nm(p) : t('rl.watch')))}</b>${p ? `<small>📍 ${esc(nm(p))}</small>` : ''}</span></button>`;
}

/** Home: a row of the newest reels. Empty until the feed has loaded (then the caller fills #homeReels). */
export function reelsStripHtml() {
  const list = reelList().slice(0, 12);
  if (!list.length) return '';
  return `<section class="section reels-strip"><div class="section-head"><div><h2>${t('rl.title')}</h2><p class="sub">${t('rl.sub')}</p></div>
      <button class="link-btn" data-q="reels">${t('h.seeAll')}</button></div>
    <div class="hscroll">${list.map(tileHtml).join('')}</div></section>`;
}
/** Moments: every reel, newest first. */
export function reelsGridHtml() {
  const list = reelList();
  if (!list.length) return '';
  return `<section class="reels-all" id="reelsAll"><div class="section-head"><div><h2>${t('rl.title')}</h2><p class="sub">${t('rl.sub')}</p></div>
      <span class="fine">${t('rl.count', { n: list.length })}</span></div>
    <div class="reel-grid">${list.map(tileHtml).join('')}</div></section>`;
}
/** Click handler for either list. Returns true when it handled the click. */
export function reelsClick(e) {
  const i = e.target.closest('[data-reel]')?.dataset.reel;
  if (i == null) return false;
  openReel(+i, 'tile');
  return true;
}

/* The player. Time spent watching is recorded when the sheet closes (or moves to the next reel or a pandal). */
let watching = null;
function stopWatching() {
  if (!watching) return;
  const secs = Math.round((Date.now() - watching.t0) / 1000);
  track('reel_watch', { place: watching.pandal, kind: watching.pandal ? 'pandal' : null, d: `${watching.id}:${secs}` });
  watching = null;
}
export function openReel(i, from = 'tile') {
  const list = reelList(), r = list[i], src = r && embedUrl(r.url);
  if (!src) return;
  stopWatching();
  if (radio.playing()) radio.pause();   // one sound at a time
  const p = r.pandal && idx.pandal[r.pandal];
  track('reel_open', { place: r.pandal || null, kind: p ? 'pandal' : null, d: `${r.id}:${from}` });
  openSheet(`<div class="reel-sheet">
      <div class="reel-player ${r.src}"><iframe src="${esc(src)}" title="${esc(r.title || t('rl.watch'))}" allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
        allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe></div>
      <div class="reel-meta">${r.sponsored ? `<span class="sponsored">${t('of.sponsored')}</span>` : ''}${r.title ? `<b>${esc(r.title)}</b>` : ''}
        <span class="fine">${r.credit ? `${esc(r.credit)} · ` : ''}<a href="${esc(r.url)}" target="_blank" rel="noopener">${t('rl.on', { app: SRC[r.src] })}</a></span></div>
      <div class="reel-actions">
        ${p ? `<button type="button" class="btn primary" data-rp="${esc(r.pandal)}">📍 ${t('rl.pandal', { name: esc(nm(p)) })}</button>` : ''}
        ${list.length > 1 ? `<button type="button" class="btn" data-rn>${t('rl.next')} ›</button>` : ''}
      </div></div>`,
  (body) => {
    watching = { id: r.id, pandal: r.pandal || null, t0: Date.now() };
    body.onclick = (e) => {
      const pid = e.target.closest('[data-rp]')?.dataset.rp;
      if (pid) { track('reel_pandal', { place: pid, kind: 'pandal', d: r.id }); return openPlace(pid); }
      if (e.target.closest('[data-rn]')) return openReel((i + 1) % list.length, 'next');
    };
  },
  () => { stopWatching(); document.querySelector('#sheetBody .reel-player iframe')?.remove(); });   // stop the video
}

/** "See all" on Home: the full list in Moments. */
export function showAllReels(go) {
  go('moments');
  requestAnimationFrame(() => {
    const el = document.getElementById('reelsAll');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' }); else toast(t('rl.none'));
  });
}
