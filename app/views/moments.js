/* Moments: this year's community photos/videos (filterable by area and on-site verification), then the pujo
 * archive: real Durga Puja photos from Wikimedia Commons by year, each credited, so the tab is never empty. */
import { S, G, idx, t, community, zs, esc, icon, nm } from '../state.js';
import { $, registerView } from '../ui.js';
import { thumbHtml, momentSheet, momentCache, uploadSheet, photoSheet } from '../sheets.js';
import { areaChipsHtml, handleAreaClick, inArea } from '../filters.js';

const PAGE = 30, AR_PAGE = 24;
let pending = 0;
// Archive (app/data/archive.json): loaded on first visit.
const ar = { photos: null, year: 'all', shown: AR_PAGE };
function loadArchive() {
  if (ar.photos) return;
  ar.photos = [];
  fetch('data/archive.json').then((r) => r.json()).then((d) => { ar.photos = d.photos || []; paint(); }).catch(() => {});
}
function archiveList() {
  const m = S.moments;
  return (ar.photos || []).filter((p) => (ar.year === 'all' || p.year === +ar.year) && (m.region === 'all' || (p.zone && inArea(m, p.zone))));
}
function archiveHtml() {
  if (!ar.photos?.length) return '';
  const years = [...new Set(ar.photos.map((p) => p.year))].sort((a, b) => b - a).slice(0, 6);
  const list = archiveList(), show = list.slice(0, ar.shown);
  return `<section class="archive"><div class="section-head"><h2>${t('ar.title')}</h2><span class="fine">${t('ar.count', { n: list.length })}</span></div>
    <p class="fine pad-x">${t('ar.sub')}</p>
    <div class="chips scroll pad-x ar-years">${['all', ...years].map((y) => `<button class="chip sm" data-ary="${y}" aria-pressed="${String(ar.year) === String(y)}">${y === 'all' ? t('ar.all') : y}</button>`).join('')}</div>
    ${show.length ? `<div class="grid-photos ar-grid">${show.map((p, i) => `<button class="thumb ar" data-ar="${i}" aria-label="${esc(p.title)}">
        <img loading="lazy" decoding="async" referrerpolicy="no-referrer" src="${esc(p.src)}" alt="">
        <span class="ar-year">${p.year}</span>${p.pandal && idx.pandal[p.pandal] ? `<span class="ar-name">${esc(nm(idx.pandal[p.pandal]))}</span>` : ''}</button>`).join('')}</div>`
    : `<p class="fine pad-x">${t('ar.none')}</p>`}
    ${list.length > ar.shown ? `<div class="center" style="margin:14px"><button class="btn sm" id="arMore">${t('m.more')}</button></div>` : ''}
    <p class="fine pad-x credit">${t('ar.credit')}</p></section>`;
}

async function load(reset = false) {
  const m = S.moments;
  if (m.loading || (!reset && m.done)) return;
  if (reset) { m.items = []; m.done = false; }
  m.loading = true; paint();
  try {
    const placeIds = m.region === 'all' ? null : [...G.data.pandals, ...G.data.food].filter((p) => inArea(m, p.zone)).map((p) => p.id);
    const before = m.items.length ? m.items[m.items.length - 1].created_at : null;
    const items = await community.feed({ placeIds, onSiteOnly: m.onSite, before, limit: PAGE });
    m.items.push(...items); momentCache.push(...items);
    m.done = items.length < PAGE; m.error = false;
  } catch { m.error = true; }
  m.loading = false; paint();
}

function paint() {
  const el = $('#view-moments'), m = S.moments;
  const live = !community.enabled ? `<div class="notice"><b>${t('m.soonTitle')}</b><span>${t('m.soonBody')}</span></div>`
    : `<div class="toolbar"><label class="toggle small" style="font-weight:500"><input type="checkbox" id="onSiteOnly" ${m.onSite ? 'checked' : ''}> <span>${icon('pin', 'sm')} ${t('m.onSiteOnly')}</span></label>
      ${pending ? `<span class="pill">${t('m.pendingN', { n: pending })}</span>` : ''}</div>
    ${m.items.length ? `<div class="grid-photos">${m.items.map(thumbHtml).join('')}</div>` : m.loading ? '' : `<div class="first-moment">${icon('camera')}<div><b>${m.error ? t('m.offline') : t('m.firstTitle')}</b><span>${t('m.firstSub')}</span></div><button class="btn primary sm" id="firstMoment">${t('m.add')}</button></div>`}
    <div class="center" style="margin:12px">${m.loading ? `<span class="fine">${t('m.loading')}</span>` : !m.done && m.items.length ? `<button class="btn sm" id="moreMoments">${t('m.more')}</button>` : ''}</div>`;
  el.innerHTML = `<div class="view-title"><h2>${t('m.title')}</h2><p>${t('m.subtitle')}</p></div>
    <div style="margin-top:12px">${areaChipsHtml(m)}</div>
    <section class="this-year"><div class="section-head"><h2>${t('m.thisYear')}</h2></div>${live}</section>
    ${archiveHtml()}`;
  el.onclick = (e) => {
    if (handleAreaClick(e, m)) { ar.shown = AR_PAGE; return community.enabled ? load(true) : paint(); }
    const y = e.target.closest('[data-ary]')?.dataset.ary; if (y) { ar.year = y; ar.shown = AR_PAGE; return paint(); }
    if (e.target.closest('#arMore')) { ar.shown += AR_PAGE; return paint(); }
    const ai = e.target.closest('[data-ar]')?.dataset.ar; if (ai != null) return photoSheet(archiveList()[+ai]);
    const id = e.target.closest('[data-moment]')?.dataset.moment; if (id) return momentSheet(m.items.find((x) => x.id === id));
    if (e.target.closest('#moreMoments')) return load();
    if (e.target.closest('#firstMoment')) return uploadSheet();
  };
  const os = $('#onSiteOnly', el); if (os) os.onchange = () => { m.onSite = os.checked; load(true); };
}

function render() {
  loadArchive();
  paint();
  if (community.enabled && !S.moments.items.length && !S.moments.loading) load(true);
  community.pendingMoments().then((list) => { if (list.length !== pending) { pending = list.length; paint(); } }).catch(() => {});
}

export function setupMoments() {
  $('#fabAdd').onclick = () => uploadSheet();
  community.on((type) => { if ((type === 'moment' || type === 'flushed') && S.view === 'moments') load(true); });
}

registerView('moments', { render });
