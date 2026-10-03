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

/** The whole region → area choice as one native dropdown: 'all', 'r:<region>' or 'a:<zone>'. */
export const areaValue = (sel) => (sel.area !== 'all' ? 'a:' + sel.area : sel.region !== 'all' ? 'r:' + sel.region : 'all');
export function areaSelectHtml(sel, id) {
  const v = areaValue(sel), o = (val, label) => `<option value="${val}" ${v === val ? 'selected' : ''}>${esc(label)}</option>`;
  return `<select id="${id}" aria-label="${t('f.areas')}">${o('all', t('zones.all'))}${G.data.regions.map((r) => {
    const zs = r.zone_ids.map((zid) => idx.zone[zid]).filter(Boolean);
    return `<optgroup label="${esc(rname(r))}">${o('r:' + r.id, t('f.allIn', { region: rname(r) }))}${zs.length > 1 ? zs.map((z) => o('a:' + z.id, zshort(z))).join('') : ''}</optgroup>`;
  }).join('')}</select>`;
}
/** Apply a dropdown value from areaSelectHtml to `sel` in place. */
export function setAreaValue(sel, v) {
  const [k, id] = v.split(':');
  if (k === 'a' && idx.zone[id]) Object.assign(sel, selectArea(id));
  else if (k === 'r' && idx.region[id]) Object.assign(sel, { region: id, area: 'all' });
  else Object.assign(sel, { region: 'all', area: 'all' });
}
