/* Searchable "Start from" picker: my location, metro/rail stations by line, pandals by region and area, parking by region. */
import { G, idx, t, esc, nm, zs, icon, btn } from './state.js';
import { openSheet, closeSheet, $ } from './ui.js';
import { rname } from './filters.js';

const LINES = ['blue', 'green', 'purple', 'orange', 'suburban'];
const cap = (l) => l[0].toUpperCase() + l.slice(1);

export function startLabel(val) {
  if (!val || val === 'me') return t('f.me');
  const [k, id] = val.split(':');
  const r = k === 't' ? idx.transit[id] : k === 'p' ? idx.parking[id] : idx.pandal[id];
  if (!r) return t('f.me');
  return k === 't' ? `🚇 ${r.name}` : k === 'p' ? `🅿 ${r.name}` : `🛕 ${nm(r)}`;
}

/** Resolve a start value to a point: 'me', 't:<station>', 'p:<parking>', 'pd:<pandal>'. */
export function startRecord(val) {
  const [k, id] = (val || '').split(':');
  const r = k === 't' ? idx.transit[id] : k === 'p' ? idx.parking[id] : k === 'pd' ? idx.pandal[id] : null;
  return r ? { id: r.id, name: k === 'pd' ? nm(r) : r.name, lat: r.lat, lng: r.lng } : null;
}

function groups() {
  const g = [{ title: '', items: [{ v: 'me', label: t('f.me'), sub: '', ic: 'locate' }] }];
  for (const l of LINES) {
    const st = G.data.transit.filter((s) => s.line === l);
    if (st.length) g.push({ title: t('f.line', { line: cap(l) }), items: st.map((s) => ({ v: 't:' + s.id, label: s.name, sub: '', ic: 'metro', line: l })) });
  }
  for (const r of G.data.regions) {
    const items = r.zone_ids.flatMap((zid) => (idx.zone[zid]?.pandal_ids || []).map((pid) => idx.pandal[pid]))
      .sort((a, b) => b.popularity - a.popularity).map((p) => ({ v: 'pd:' + p.id, label: nm(p), sub: zs(idx.zone[p.zone]), ic: 'star', alt: p.name }));
    if (items.length) g.push({ title: `${t('f.pandalsIn', { region: rname(r) })}`, items });
  }
  const parks = G.data.parking.map((p) => ({ v: 'p:' + p.id, label: p.name, sub: idx.zone[p.zone] ? zs(idx.zone[p.zone]) : '', ic: 'car' }));
  g.push({ title: t('f.parkingGroup'), items: parks });
  return g;
}

export function startPickerSheet(current, onPick) {
  const all = groups();
  const paint = (q) => {
    const needle = q.trim().toLowerCase();
    return all.map((grp) => {
      const items = needle ? grp.items.filter((i) => `${i.label} ${i.alt || ''} ${i.sub}`.toLowerCase().includes(needle)) : grp.items;
      if (!items.length) return '';
      return `${grp.title ? `<h3 class="sh">${esc(grp.title)}</h3>` : ''}<ul class="mini-list">${items.slice(0, needle ? 50 : 400).map((i) =>
        `<li data-pick="${i.v}" ${btn(i.v === current ? 'aria-current="true"' : '')}><span>${icon(i.ic, 'sm')} ${i.line ? `<span class="line-${i.line}">●</span> ` : ''}${esc(i.label)}${i.sub ? ` <small>· ${esc(i.sub)}</small>` : ''}</span>${i.v === current ? icon('check', 'sm') : ''}</li>`).join('')}</ul>`;
    }).join('') || `<p class="fine">${t('h.noResults')}</p>`;
  };
  openSheet(`<h2 class="title">${t('f.start')}</h2>
    <div class="search" style="margin:10px 0 0">${icon('search')}<input id="pickSearch" type="search" autocomplete="off" placeholder="${t('f.startSearch')}" aria-label="${t('f.startSearch')}"></div>
    <div id="pickList" style="margin-top:4px">${paint('')}</div>`,
  (el) => {
    const input = $('#pickSearch', el), list = $('#pickList', el);
    input.oninput = () => { list.innerHTML = paint(input.value); };
    list.onclick = (e) => { const li = e.target.closest('[data-pick]'); if (li) { closeSheet(); onPick(li.dataset.pick); } };
  });
}
