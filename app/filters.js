/* Two-level place filter: Region (North, Central, South, East, Howrah), then Area within it.
 * A selection is { region: 'all' | regionId, area: 'all' | zoneId }. */
import { G, idx, t, esc, bn } from './state.js';

export const regionOf = (zoneId) => idx.zone[zoneId]?.region;
export const rname = (r) => (bn() && r.name_bn) || r.name;
const zshort = (z) => (bn() && z.short_bn) || z.short;

/** Does a place in `zoneId` fall inside the selection? */
export const inArea = (sel, zoneId) =>
  (sel.region === 'all' || regionOf(zoneId) === sel.region) && (sel.area === 'all' || zoneId === sel.area);

/** The zone ids a selection covers. */
export const areasOf = (sel) => G.data.zones.filter((z) => inArea(sel, z.id)).map((z) => z.id);

export function areaChipsHtml(sel) {
  const regions = G.data.regions;
  const row1 = [`<button class="chip" data-fr="all" aria-pressed="${sel.region === 'all'}">${t('zones.all')}</button>`,
    ...regions.map((r) => `<button class="chip" data-fr="${r.id}" aria-pressed="${sel.region === r.id}"><span class="dot" style="background:${r.color}"></span>${esc(rname(r))}</button>`)].join('');
  let row2 = '';
  if (sel.region !== 'all') {
    const r = idx.region[sel.region];
    const zs = r.zone_ids.map((id) => idx.zone[id]).filter(Boolean);
    if (zs.length > 1) {
      row2 = `<div class="chips sub" role="group" aria-label="${t('f.areas')}">
        <button class="chip sm" data-fa="all" aria-pressed="${sel.area === 'all'}">${t('f.allIn', { region: rname(r) })}</button>
        ${zs.map((z) => `<button class="chip sm" data-fa="${z.id}" aria-pressed="${sel.area === z.id}"><span class="dot" style="background:${z.color}"></span>${esc(zshort(z))}</button>`).join('')}</div>`;
    }
  }
  return `<div class="chips" role="group" aria-label="${t('f.regions')}">${row1}</div>${row2}`;
}

/** Click handler helper: updates `sel` in place and returns true if the click was a filter chip. */
export function handleAreaClick(e, sel) {
  const r = e.target.closest('[data-fr]')?.dataset.fr;
  if (r) { sel.region = r; sel.area = 'all'; return true; }
  const a = e.target.closest('[data-fa]')?.dataset.fa;
  if (a) { sel.area = a; return true; }
  return false;
}

/** Selection that shows a single area (for deep links from Home). */
export const selectArea = (zoneId) => ({ region: regionOf(zoneId) || 'all', area: zoneId });

/** Bounding box covering a selection, for fitting the map. */
export function bboxOf(sel) {
  const zs = areasOf(sel).map((id) => idx.zone[id]);
  if (!zs.length || (sel.region === 'all')) return null;
  return [[Math.min(...zs.map((z) => z.bbox[0][0])), Math.min(...zs.map((z) => z.bbox[0][1]))],
    [Math.max(...zs.map((z) => z.bbox[1][0])), Math.max(...zs.map((z) => z.bbox[1][1]))]];
}
