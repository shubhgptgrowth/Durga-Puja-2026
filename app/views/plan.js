/* Plan: curated trails and the time-budgeted custom route builder. */
import { hav, orderRoute, routeUrls, hhmm, encodePlan } from '../core.js';
import {
  S, G, idx, t, store, ll, M, nm, zs, dn, zoneOf, esc, km, fmt, crowdIndex, crowdWord, dayFactor, stepsFor, kcalFor, btn, icon,
} from '../state.js';
import { $, go, registerView, makeMap, toast, getFix } from '../ui.js';
import { openPlace } from '../sheets.js';
import { startWalk, walking } from '../actions.js';

let planSel = new Set(), seg = 'curated', planMap = null;
const form = { start: 't:kalighat', time: '17:00', stars: '4', budget: '240', brisk: false };

/* ---------------- routing ---------------- */
function routeZone(start, pandals, clock, brisk) {
  const pts = pandals.map(ll), order = orderRoute(ll(start), pts);
  const speed = ((brisk ? M().walk_kmh_brisk : M().walk_kmh_crowd) * 1000) / 60;
  let cur = ll(start), walk = 0, wmin = 0, dwell = 0; const stops = [];
  for (const i of order) {
    const p = pandals[i], d = hav(cur, pts[i]) * M().detour, w = Math.round(d / speed);
    clock += w;
    const c = crowdIndex(p.crowd_base, dayFactor(), Math.floor(clock / 60));
    const dw = Math.round(p.visit_min * (0.6 + (0.8 * c) / 100));
    stops.push({ pandal: p.id, walk_m: Math.round(d), walk_min: w, arrive: hhmm(clock), crowd: c, dwell_min: dw });
    clock += dw; walk += d; wmin += w; dwell += dw; cur = pts[i];
  }
  return { stops, walk, wmin, dwell, clock };
}
function entryStation(pandals) {
  let best, bd = Infinity;
  for (const s of G.data.transit) for (const p of pandals) { const d = hav(ll(s), ll(p)); if (d < bd) { bd = d; best = s; } }
  return best;
}
function planMulti(start, zones, minStars, startMin, brisk, exclude) {
  const groups = zones.map((z) => G.data.pandals.filter((p) => p.zone === z && p.popularity >= minStars && !exclude.has(p.id))).filter((g) => g.length);
  const ordered = []; let here = ll(start); const rest = [...groups];
  while (rest.length) { // visit the nearest zone next
    rest.sort((a, b) => Math.min(...a.map((p) => hav(here, ll(p)))) - Math.min(...b.map((p) => hav(here, ll(p)))));
    const g = rest.shift(); ordered.push(g); here = ll(g[g.length - 1]);
  }
  let clock = startMin, from = start; const segs = []; let walk = 0, wmin = 0, dwell = 0, ride = 0, n = 0;
  ordered.forEach((g, gi) => {
    const nearestM = Math.min(...g.map((p) => hav(ll(from), ll(p))));
    let segStart = from;
    if (nearestM > 1800) { // too far to walk, so ride to the zone's entry station
      const st = entryStation(g);
      const rm = Math.round((hav(ll(from), ll(st)) * 1.25) / ((18 * 1000) / 60)) + 10;
      segs.push({ type: 'ride', to: st.id, depart: hhmm(clock), ride_min: rm });
      clock += rm; ride += rm; segStart = st;
    }
    const r = routeZone(segStart, g, clock, brisk);
    segs.push({ type: 'walk', zone: g[0].zone, stops: r.stops });
    clock = r.clock; walk += r.walk; wmin += r.wmin; dwell += r.dwell; n += r.stops.length;
    from = idx.pandal[r.stops[r.stops.length - 1].pandal];
  });
  return { segments: segs, totals: { pandals: n, walk_m: walk, walk_min: wmin, dwell_min: dwell, ride_min: ride, brisk }, endMin: clock };
}

function startPoint(val) {
  if (val === 'me') return S.me ? Promise.resolve({ id: 'me', lat: S.me[0], lng: S.me[1] }) : getFix().then((f) => ({ id: 'me', lat: f.lat, lng: f.lng }));
  const [k, id] = val.split(':');
  const r = k === 't' ? idx.transit[id] : idx.parking[id];
  return Promise.resolve({ id: r.id, name: r.name, lat: r.lat, lng: r.lng });
}
const ptName = (pt) => (pt.id === 'me' ? t('plan.me') : pt.name);

export async function buildCustom() {
  if (!planSel.size) return toast(t('plan.pickZone'));
  const zones = [...planSel], minStars = +form.stars, budget = +form.budget, brisk = form.brisk;
  const [h, m] = form.time.split(':').map(Number), startMin = h * 60 + m;
  let start;
  try { start = await startPoint(form.start); } catch { return toast(t('loc.fail')); }
  const exclude = new Set();
  let res = planMulti(start, zones, minStars, startMin, brisk, exclude);
  const total = (r) => r.totals.walk_min + r.totals.dwell_min + r.totals.ride_min;
  // Over budget? Drop the stop that costs the most minutes (detour + dwell) per unit of fame, then re-plan.
  const speed = ((brisk ? M().walk_kmh_brisk : M().walk_kmh_crowd) * 1000) / 60;
  while (total(res) > budget && res.totals.pandals > 1) {
    const all = res.segments.filter((s) => s.type === 'walk').flatMap((s) => s.stops);
    const pts = [ll(start), ...all.map((x) => ll(idx.pandal[x.pandal]))];
    let worst = null, worstScore = -Infinity;
    all.forEach((x, i) => {
      const prev = pts[i], cur = pts[i + 1], next = pts[i + 2], wm = (a, b) => hav(a, b) * M().detour;
      const detour = wm(prev, cur) + (next ? wm(cur, next) - wm(prev, next) : 0);
      const score = (detour / speed + x.dwell_min) / idx.pandal[x.pandal].popularity ** 2;
      if (score > worstScore) { worstScore = score; worst = x.pandal; }
    });
    exclude.add(worst);
    res = planMulti(start, zones, minStars, startMin, brisk, exclude);
  }
  if (!res.totals.pandals) return toast(t('plan.none'));
  const params = { z: zones, s: form.start, t: form.time, r: minStars, b: budget, k: brisk ? 1 : 0, d: S.day };
  setPlan({ kind: 'custom', zones, day: S.day, start: hhmm(startMin), end: hhmm(res.endMin), startPt: start,
    segments: res.segments, totals: res.totals, skipped: exclude.size, params });
}

export function showTrail(id) {
  const it = G.data.itineraries.find((x) => x.id === id);
  if (!it) return;
  seg = 'curated';
  const first = it.segments.find((s) => s.type === 'walk');
  setPlan({
    kind: 'trail', id: it.id, day: it.day, start: it.start_time, end: it.end_time, startPt: idx.transit[first.start],
    segments: it.segments.map((s) => (s.type === 'ride' ? { type: 'ride', to: s.to_station, depart: s.depart, ride_min: s.ride_min } : { type: 'walk', zone: s.zone, stops: s.stops })),
    totals: { pandals: it.pandal_count, walk_m: it.totals.walk_m ?? it.totals.walk_km * 1000, walk_min: it.totals.walk_min, dwell_min: it.totals.dwell_min, ride_min: it.totals.ride_min, brisk: false },
  });
}
function setPlan(plan) { S.plan = plan; store.set('activePlan', plan); if (S.view === 'plan') render(true); }

export function presetPlan(zones, startId) {
  planSel = new Set(zones); seg = 'custom';
  form.start = 't:' + (startId || zoneOf(zones[0]).route.start);
  go('plan'); buildCustom();
}
export function openSharedPlan(p) {
  seg = 'custom';
  if (!p) return go('plan');
  planSel = new Set(p.z.filter((z) => idx.zone[z]));
  const ok = p.s === 'me' || (p.s.startsWith('t:') && idx.transit[p.s.slice(2)]) || (p.s.startsWith('p:') && idx.parking[p.s.slice(2)]);
  if (ok) form.start = p.s;
  if (/^\d\d:\d\d$/.test(p.t)) form.time = p.t;
  if (p.r) form.stars = String(p.r);
  if (p.b) form.budget = String(p.b);
  form.brisk = !!p.k;
  if (p.d && idx.day[p.d]) { S.day = p.d; $('#daySelect').value = p.d; }
  go('plan');
  if (planSel.size) { buildCustom(); toast(t('share.loaded')); }
}
export const stopsOf = (plan) => (plan?.segments || []).filter((s) => s.type === 'walk').flatMap((s) => s.stops);
export const planValid = (plan) => !!plan?.kind && !!plan.startPt && stopsOf(plan).length > 0 && stopsOf(plan).every((x) => idx.pandal[x.pandal]);
const planTitle = (plan) => {
  if (plan.kind === 'trail') { const it = G.data.itineraries.find((i) => i.id === plan.id); return (S.prefs.lang === 'bn' && it?.name_bn) || it?.name || ''; }
  return (plan.zones || []).map((z) => zs(zoneOf(z))).join(' + ');
};
const shareUrl = (plan) => location.origin + location.pathname + (plan.kind === 'trail' ? '#trail=' + plan.id : '#plan=' + encodePlan(plan.params));
async function share(plan) {
  const url = shareUrl(plan), text = t('share.text', { title: planTitle(plan) });
  try {
    if (navigator.share) { await navigator.share({ title: 'Pujo Parikrama', text, url }); return; }
    await navigator.clipboard.writeText(`${text}\n${url}`); toast(t('share.copied'));
  } catch (e) { if (e?.name !== 'AbortError') prompt(t('share.copyPrompt'), url); }
}

/* ---------------- render ---------------- */
function formHtml() {
  const lines = ['blue', 'green', 'purple', 'orange', 'suburban'], cap = (l) => l[0].toUpperCase() + l.slice(1);
  const opt = (v, label) => `<option value="${v}" ${form.start === v ? 'selected' : ''}>${label}</option>`;
  return `<form id="planForm" class="form">
    <fieldset><legend>${t('f.zones')}</legend><div class="chips wrap" id="planZones">${G.data.zones.map((z) => `<button type="button" class="chip" data-pz="${z.id}" aria-pressed="${planSel.has(z.id)}"><span class="dot" style="background:${z.color}"></span>${esc(zs(z))}</button>`).join('')}</div></fieldset>
    <div class="grid2">
      <label>${t('f.start')}<select id="planStart">${opt('me', t('f.me'))}
        ${lines.map((l) => `<optgroup label="${t('f.line', { line: cap(l) })}">${G.data.transit.filter((s) => s.line === l).map((s) => opt('t:' + s.id, esc(s.name))).join('')}</optgroup>`).join('')}
        <optgroup label="${t('f.parkingGroup')}">${G.data.parking.map((p) => opt('p:' + p.id, '🅿 ' + esc(p.name))).join('')}</optgroup></select></label>
      <label>${t('f.time')}<input type="time" id="planTime" value="${form.time}"></label>
      <label>${t('f.stars')}<select id="planStars">${['1', '3', '4', '5'].map((v) => `<option value="${v}" ${form.stars === v ? 'selected' : ''}>${t('stars.' + v)}</option>`).join('')}</select></label>
      <label>${t('f.budget')}<select id="planBudget">${['120', '180', '240', '360', '600'].map((v) => `<option value="${v}" ${form.budget === v ? 'selected' : ''}>${t('budget.' + v)}</option>`).join('')}</select></label>
    </div>
    <label class="toggle"><input type="checkbox" id="planBrisk" ${form.brisk ? 'checked' : ''}> <span>${t('f.brisk')}</span></label>
    <button type="submit" class="btn primary block">${icon('route')} ${t('f.build')}</button>
  </form>`;
}
function trailsHtml() {
  return `<div class="list">${G.data.itineraries.map((it) => {
    const x = it.totals;
    return `<div class="card trail" data-trail="${it.id}" ${btn()}>
      <div style="display:flex;justify-content:space-between;gap:8px;align-items:start"><h3>${esc((S.prefs.lang === 'bn' && it.name_bn) || it.name)}</h3><span class="pill">${esc(dn(idx.day[it.day]))} · ${it.start_time}</span></div>
      <p>${esc((S.prefs.lang === 'bn' && it.blurb_bn) || it.blurb)}</p>
      <div class="row"><span>${t('it.pandals', { n: it.pandal_count })}</span><span>${x.walk_km} km</span><span>${fmt(stepsFor(x.walk_m ?? x.walk_km * 1000))} ${t('kpi.steps')}</span><span>${t('it.dur', { h: Math.floor(x.duration_min / 60), m: x.duration_min % 60 })}</span></div>
    </div>`;
  }).join('')}</div>`;
}
function resultHtml(plan) {
  const x = plan.totals, stops = stopsOf(plan);
  const pts = [ll(plan.startPt), ...stops.map((s) => ll(idx.pandal[s.pandal]))];
  const legs = routeUrls(pts);
  let n = 0, lastFood = -9; const used = new Set();
  const tl = [`<li class="start"><div class="t">${plan.start}</div><div class="nm">${t('tl.start', { name: esc(ptName(plan.startPt)) })}</div></li>`];
  for (const s of plan.segments) {
    if (s.type === 'ride') { tl.push(`<li class="ride"><div class="t">${s.depart}</div><div class="nm">${t('tl.ride', { name: esc(idx.transit[s.to]?.name || '') })}</div><div class="sub">${t('tl.rideMin', { n: s.ride_min })}</div></li>`); continue; }
    for (const st of s.stops) {
      n++;
      const p = idx.pandal[st.pandal], hour = +st.arrive.slice(0, 2), meal = (hour >= 12 && hour <= 14) || (hour >= 19 && hour <= 21);
      let eat = '';
      const f = p.food.filter((ff) => ff.distance_m <= 800).map((ff) => idx.food[ff.id]).find((ff) => !used.has(ff.id));
      if (f && (n - lastFood >= 3 || (meal && n - lastFood >= 2))) { used.add(f.id); lastFood = n; eat = `<div class="eat">${t('tl.eat', { dish: esc(f.dishes[0]), place: esc(f.name) })}</div>`; }
      tl.push(`<li data-n="${n}" data-place="${st.pandal}" ${btn()}><div class="t">${st.arrive}</div><div class="nm">${esc(nm(p))}${S.checkins[st.pandal] ? ' ✓' : ''}</div>
        <div class="sub">${st.walk_m ? `${t('tl.walk', { m: st.walk_m })} · ` : ''}${crowdWord(st.crowd)} · ${t('tl.inside', { n: st.dwell_min })}</div>${eat}</li>`);
    }
  }
  return `<div class="card plan-sum">
      <h3>${esc(planTitle(plan))}</h3>
      <div class="fine">${t('plan.sub', { day: dn(idx.day[plan.day]), from: plan.start, to: plan.end, start: esc(ptName(plan.startPt)) })}${plan.skipped ? ` · ${t('plan.dropped', { n: plan.skipped })}` : ''}</div>
      <div class="kpis"><div><b>${x.pandals}</b><span>${t('kpi.pandals')}</span></div><div><b>${km(x.walk_m)}</b><span>${t('kpi.km')}</span></div><div><b>${fmt(stepsFor(x.walk_m))}</b><span>${t('kpi.steps')}</span></div><div><b>${fmt(kcalFor(x.walk_min, x.dwell_min, x.brisk))}</b><span>${t('kpi.kcal')}</span></div></div>
      <div class="btn-row"><button class="btn primary" id="planWalk">${icon('walk')} ${t('plan.startWalk')}</button><button class="btn" id="planShare">${icon('share')} ${t('plan.share')}</button></div>
      <div class="btn-row" style="margin-top:8px">${legs.map((u, i) => `<a class="btn sm" target="_blank" rel="noopener" href="${u}">${t('plan.maps')}${legs.length > 1 ? ` · ${t('plan.leg', { n: i + 1 })}` : ''}</a>`).join('')}</div>
    </div>
    <div id="planMap" class="map short" style="margin:12px 16px;border-radius:16px;overflow:hidden"></div>
    <ol class="timeline">${tl.join('')}</ol>`;
}

function render(scrollToResult = false) {
  const el = $('#view-plan'), plan = planValid(S.plan) ? S.plan : null;
  el.innerHTML = `<div class="view-title"><h2>${t('plan.title')}</h2><p>${t('plan.subtitle')}</p></div>
    <div class="seg" role="tablist" style="margin-top:12px">
      <button role="tab" data-seg="curated" aria-selected="${seg === 'curated'}">${t('seg.curated')}</button>
      <button role="tab" data-seg="custom" aria-selected="${seg === 'custom'}">${t('seg.custom')}</button></div>
    ${seg === 'curated' ? trailsHtml() : formHtml()}
    <div id="planResult" style="margin-top:16px">${plan ? resultHtml(plan) : ''}</div>`;
  wire(el, plan);
  if (plan) drawPlanMap(plan);
  if (scrollToResult && plan) window.scrollTo({ top: $('#planResult').getBoundingClientRect().top + window.scrollY - $('.topbar').offsetHeight - 8, behavior: 'smooth' });
}
function drawPlanMap(plan) {
  if (planMap) { planMap.remove(); planMap = null; }
  planMap = makeMap($('#planMap'));
  if (!planMap) return;
  const stops = stopsOf(plan), pts = [ll(plan.startPt), ...stops.map((s) => ll(idx.pandal[s.pandal]))];
  L.polyline(pts, { color: '#9F1239', weight: 4, opacity: .85, dashArray: '2 8', lineCap: 'round' }).addTo(planMap);
  L.marker(pts[0], { icon: L.divIcon({ className: '', html: '<div class="seq" style="background:#1C1917">▶</div>', iconSize: [26, 26] }), keyboard: false }).addTo(planMap);
  stops.forEach((st, i) => L.marker(ll(idx.pandal[st.pandal]), { icon: L.divIcon({ className: '', html: `<div class="seq">${i + 1}</div>`, iconSize: [26, 26] }), title: nm(idx.pandal[st.pandal]) })
    .on('click', () => openPlace(st.pandal)).addTo(planMap));
  planMap.fitBounds(L.latLngBounds(pts), { padding: [24, 24] });
}
function wire(el, plan) {
  el.onclick = (e) => {
    const sg = e.target.closest('[data-seg]')?.dataset.seg; if (sg) { seg = sg; return render(); }
    const pz = e.target.closest('[data-pz]')?.dataset.pz;
    if (pz) { planSel.has(pz) ? planSel.delete(pz) : planSel.add(pz); e.target.closest('[data-pz]').setAttribute('aria-pressed', planSel.has(pz)); return; }
    const tr = e.target.closest('[data-trail]')?.dataset.trail; if (tr) return showTrail(tr);
    const pl = e.target.closest('[data-place]')?.dataset.place; if (pl) return openPlace(pl);
    if (e.target.closest('#planWalk')) { go('me'); if (!walking()) startWalk(); return; }
    if (e.target.closest('#planShare')) return share(plan);
  };
  const f = $('#planForm', el);
  if (f) {
    f.onchange = () => { form.start = $('#planStart').value; form.time = $('#planTime').value || '17:00'; form.stars = $('#planStars').value; form.budget = $('#planBudget').value; form.brisk = $('#planBrisk').checked; };
    f.onsubmit = (e) => { e.preventDefault(); f.onchange(); buildCustom(); };
  }
}

registerView('plan', { render: () => render(false), onShow: () => setTimeout(() => planMap?.invalidateSize(), 60) });
