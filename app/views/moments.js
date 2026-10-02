/* Moments: the community photo/video feed, filterable by zone and on-site verification. */
import { S, G, t, community, zs, esc, icon } from '../state.js';
import { $, registerView } from '../ui.js';
import { thumbHtml, momentSheet, momentCache, uploadSheet } from '../sheets.js';
import { areaChipsHtml, handleAreaClick, inArea } from '../filters.js';

const PAGE = 30;
let pending = 0;

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
  if (!community.enabled) {
    el.innerHTML = `<div class="view-title"><h2>${t('m.title')}</h2><p>${t('m.subtitle')}</p></div>
      <div class="notice" style="margin-top:16px"><b>${t('m.soonTitle')}</b><span>${t('m.soonBody')}</span></div>`;
    return;
  }
  el.innerHTML = `<div class="view-title"><h2>${t('m.title')}</h2><p>${t('m.subtitle')}</p></div>
    <div style="margin-top:12px">${areaChipsHtml(m)}</div>
    <div class="toolbar"><label class="toggle small" style="font-weight:500"><input type="checkbox" id="onSiteOnly" ${m.onSite ? 'checked' : ''}> <span>${icon('pin', 'sm')} ${t('m.onSiteOnly')}</span></label>
      ${pending ? `<span class="pill">${t('m.pendingN', { n: pending })}</span>` : ''}</div>
    ${m.items.length ? `<div class="grid-photos">${m.items.map(thumbHtml).join('')}</div>` : m.loading ? '' : `<div class="empty">${icon('camera')}<p>${m.error ? t('m.offline') : t('m.empty')}</p><button class="btn primary" id="firstMoment">${icon('camera')} ${t('m.add')}</button></div>`}
    <div class="center" style="margin:16px">${m.loading ? `<span class="fine">${t('m.loading')}</span>` : !m.done && m.items.length ? `<button class="btn sm" id="moreMoments">${t('m.more')}</button>` : ''}</div>`;
  el.onclick = (e) => {
    if (handleAreaClick(e, m)) return load(true);
    const id = e.target.closest('[data-moment]')?.dataset.moment; if (id) return momentSheet(m.items.find((x) => x.id === id));
    if (e.target.closest('#moreMoments')) return load();
    if (e.target.closest('#firstMoment')) return uploadSheet();
  };
  const os = $('#onSiteOnly', el); if (os) os.onchange = () => { m.onSite = os.checked; load(true); };
}

function render() {
  paint();
  if (community.enabled && !S.moments.items.length && !S.moments.loading) load(true);
  community.pendingMoments().then((list) => { if (list.length !== pending) { pending = list.length; paint(); } }).catch(() => {});
}

export function setupMoments() {
  $('#fabAdd').onclick = () => uploadSheet();
  community.on((type) => { if ((type === 'moment' || type === 'flushed') && S.view === 'moments') load(true); });
}

registerView('moments', { render });
