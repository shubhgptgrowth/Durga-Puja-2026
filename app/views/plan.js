/* My route: a 3-step wizard (areas → start point → route), with ready-made trails as a shortcut on step 1. */
import { hav, orderRoute, hhmm, encodePlan, rideOption } from '../core.js';
import {
  S, G, idx, t, store, ll, M, nm, zs, dn, zoneOf, esc, km, fmt, crowdIndex, crowdWord, dayFactor, stepsFor, kcalFor, btn, icon, loc,
} from '../state.js';
import { $, go, registerView, toast, getFix } from '../ui.js';
import { openPlace, dirUrl } from '../sheets.js';
import { startWalk, walking, visitedToday } from '../actions.js';
import { startLabel, startRecord, startPickerSheet } from '../pickers.js';
import { rname } from '../filters.js';
import { track } from '../analytics.js';

let planSel = new Set(), step = 0, inPlan = false, transitData = null, transitLoading = null;
// Bus / auto data is optional and loaded lazily (app/data/transit.json, built from OpenStreetMap).
function loadTransit() {
  transitLoading ||= fetch('data/transit.json').then((r) => (r.ok ? r.json() : null)).then((d) => { transitData = d; if (d && S.view === 'plan' && planValid(S.plan)) render(); }).catch(() => null);
  return transitLoading;
}
function rideText(opt, toName) {
  if (opt.mode === 'metro') return t('tl.metro', { line: opt.line[0].toUpperCase() + opt.line.slice(1), from: esc(opt.board), to: esc(opt.alight) });
  if (opt.mode === 'bus') return t('tl.bus', { routes: esc(opt.routes.join(', ')), from: esc(opt.board || '—'), to: esc(opt.alight || '—') });
  if (opt.mode === 'auto') return opt.routes ? t('tl.autoOsm', { routes: esc(opt.routes.join(', ')), from: esc(opt.board || '—') }) : t('tl.auto', { route: esc(opt.route) });
  return t('tl.cab', { name: esc(toName) });
}
// Further apart than this, two stops are a ride (auto, bus or metro), not a walk through puja crowds.
export const HOP_M = 1300;
const hopsIn = (stops) => stops.filter((x) => x.walk_m > HOP_M);
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
  const r = startRecord(val);
  return r ? Promise.resolve(r) : Promise.reject(new Error('unknown start'));
}
const fmtDay = (d) => new Date(d.date + 'T00:00:00').toLocaleDateString(loc(), { weekday: 'short', day: 'numeric', month: 'short' });
const ptName = (pt) => (pt.id === 'me' ? t('plan.me') : pt.name);

export async function buildCustom() {
  if (!planSel.size) return toast(t('plan.pickZone'));
  const zones = [...planSel], minStars = +form.stars, budget = +form.budget, brisk = form.brisk;
  track('plan', { d: `custom:${zones.length}z:${budget}m` });
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
  track('trail', { d: id });
  const first = it.segments.find((s) => s.type === 'walk');
  setPlan({
    kind: 'trail', id: it.id, day: it.day, start: it.start_time, end: it.end_time, startPt: idx.transit[first.start],
    segments: it.segments.map((s) => (s.type === 'ride' ? { type: 'ride', to: s.to_station, depart: s.depart, ride_min: s.ride_min } : { type: 'walk', zone: s.zone, stops: s.stops })),
    totals: { pandals: it.pandal_count, walk_m: it.totals.walk_m ?? it.totals.walk_km * 1000, walk_min: it.totals.walk_min, dwell_min: it.totals.dwell_min, ride_min: it.totals.ride_min, brisk: false },
  });
}
function setPlan(plan) { S.plan = plan; step = 3; store.set('activePlan', plan); if (S.view === 'plan') render(true); }

export function presetPlan(zones, startId, opts = {}) {
  track('plan', { d: 'preset:' + zones.join('+') });
  planSel = new Set(zones);
  form.start = 't:' + (startId || zoneOf(zones[0]).route.start);
  if (opts.time) form.time = opts.time;
  if (opts.budget) form.budget = String(opts.budget);
  if (opts.day && idx.day[opts.day]) { S.day = opts.day; }
  go('plan'); buildCustom();
}

/* "All of Kolkata in 6 days": one part of the city per puja day, ordered so the biggest crowds
 * (Saptami to Navami nights) land on the areas with the best metro access. Each day opens a timed route. */
export const DAYPLAN = [
  { day: 'panchami', zones: ['lake_town_dumdum', 'salt_lake'], time: '17:00', budget: 300 },
  { day: 'shashthi', zones: ['north', 'central'], time: '16:00', budget: 420 },
  { day: 'saptami', zones: ['south_lakemarket', 'south_gariahat'], time: '16:00', budget: 420 },
  { day: 'ashtami', zones: ['bhowanipore', 'kasba', 'jadavpur_santoshpur'], time: '15:00', budget: 420 },
  { day: 'navami', zones: ['southwest', 'tolly_naktala'], time: '16:00', budget: 360 },
  { day: 'dashami', zones: ['howrah', 'beleghata'], time: '09:00', budget: 180 },
];
export function dayPlanHtml() {
  return `<div class="dayplan">${DAYPLAN.filter((d) => idx.day[d.day] && d.zones.every((z) => idx.zone[z])).map((d, i) => {
    const n = d.zones.reduce((c, z) => c + idx.zone[z].pandal_ids.length, 0);
    return `<button type="button" class="dp-day" data-dayplan="${i}">
      <span class="dp-n">${i + 1}</span>
      <span class="dp-body"><b>${esc(dn(idx.day[d.day]))} · ${fmtDay(idx.day[d.day])}</b>
        <span class="dp-areas">${d.zones.map((z) => esc(zs(idx.zone[z]))).join(' + ')} · ${t('it.pandals', { n })}</span>
        <span class="dp-tip">${t('dp.' + d.day)}</span></span>
      <span class="dp-go">${icon('chev', 'sm')}</span></button>`;
  }).join('')}</div>`;
}
export function openDayPlan(i) { const d = DAYPLAN[i]; if (d) presetPlan(d.zones, null, d); }
export function openSharedPlan(p) {
  if (!p) { step = 1; return go('plan'); }
  planSel = new Set(p.z.filter((z) => idx.zone[z]));
  const ok = p.s === 'me' || !!startRecord(p.s);
  if (ok) form.start = p.s;
  if (/^\d\d:\d\d$/.test(p.t)) form.time = p.t;
  if (p.r) form.stars = String(p.r);
  if (p.b) form.budget = String(p.b);
  form.brisk = !!p.k;
  if (p.d && idx.day[p.d]) S.day = p.d;
  go('plan');
  if (planSel.size) { buildCustom(); toast(t('share.loaded')); }
}
export const stopsOf = (plan) => (plan?.segments || []).filter((s) => s.type === 'walk').flatMap((s) => s.stops);
export const planValid = (plan) => !!plan?.kind && !!plan.startPt && stopsOf(plan).length > 0 && stopsOf(plan).every((x) => idx.pandal[x.pandal]);
const planTitle = (plan) => {
  if (plan.kind === 'trail') { const it = G.data.itineraries.find((i) => i.id === plan.id); return (S.prefs.lang === 'bn' && it?.name_bn) || it?.name || ''; }
  return (plan.zones || []).map((z) => zs(zoneOf(z))).join(' + ');
};
const shareUrl = (plan) => location.origin + location.pathname + '?src=plan_share' + (plan.kind === 'trail' ? '#trail=' + plan.id : '#plan=' + encodePlan(plan.params));
async function share(plan) {
  const url = shareUrl(plan), text = t('share.text', { title: planTitle(plan) });
  try {
    if (navigator.share) { await navigator.share({ title: 'Pujo Parikrama', text, url }); return; }
    await navigator.clipboard.writeText(`${text}\n${url}`); toast(t('share.copied'));
  } catch (e) { if (e?.name !== 'AbortError') prompt(t('share.copyPrompt'), url); }
}

/* ---------------- render ---------------- */
const pickedRegions = () => G.data.regions.filter((r) => r.zone_ids.some((id) => planSel.has(id))).length;
function areasHtml() {
  const regionRows = `<div class="regions pick">${G.data.regions.map((r) => {
    const on = r.zone_ids.some((id) => planSel.has(id));
    const n = r.zone_ids.reduce((c, id) => c + (idx.zone[id]?.pandal_ids.length || 0), 0);
    const areas = r.zone_ids.map((id) => idx.zone[id]).filter(Boolean).map(zs).join(' · ');
    return `<button type="button" class="region" data-pr="${r.id}" aria-pressed="${on}" style="--zc:${r.color}">
      <span class="region-n">${on ? '✓ ' : ''}${esc(rname(r))}</span><span class="region-c">${t('it.pandals', { n })}</span><span class="region-a">${esc(areas)}</span></button>`;
  }).join('')}</div>`;
  return `<div class="wz-body"><h3 class="wz-q">${t('wz.q1')}</h3><div id="planZones">${regionRows}</div></div>
    <div class="wz-foot"><span class="fine">${pickedRegions() ? t(pickedRegions() === 1 ? 'wz.picked1' : 'wz.picked', { n: pickedRegions() }) : t('wz.pickOne')}</span>
      <button type="button" class="btn primary" id="planNext" ${planSel.size ? '' : 'aria-disabled="true"'}>${t('wz.next')} ${icon('chev', 'sm')}</button></div>
    <div class="section-head" style="margin-top:22px"><div><h2>${t('dp.title')}</h2><p class="sub">${t('dp.sub')}</p></div></div>
    ${dayPlanHtml()}
    <div class="section-head" style="margin-top:22px"><h2>${t('wz.orTrail')}</h2></div><p class="fine pad" style="margin:-4px 0 10px">${t('h.trailsSub')}</p>
    ${trailsHtml()}`;
}
function formHtml() {
  return `<form id="planForm" class="form wz-body">
    <h3 class="wz-q">${t('wz.q2')}</h3>
    <label>${t('f.day')}<select id="planDay">${G.data.meta.days.map((d) => `<option value="${d.id}" ${S.day === d.id ? 'selected' : ''}>${esc(dn(d))} · ${fmtDay(d)}</option>`).join('')}</select>
      <span class="fine" style="font-weight:400">${t('f.dayHint')}</span></label>
    <label>${t('f.start')}<button type="button" class="btn block picker-btn" id="planStartBtn">${esc(startLabel(form.start))} ${icon('chev', 'sm')}</button></label>
    <div class="grid2">
      <label>${t('f.time')}<input type="time" id="planTime" value="${form.time}"></label>
      <label>${t('f.budget')}<select id="planBudget">${['120', '180', '240', '360', '720', '600'].map((v) => `<option value="${v}" ${form.budget === v ? 'selected' : ''}>${t('budget.' + v)}</option>`).join('')}</select></label>
    </div>
    <details class="more"><summary>${t('wz.more')}</summary>
      <div class="form" style="padding:10px 0 0">
        <label>${t('f.stars')}<select id="planStars">${['1', '3', '4', '5'].map((v) => `<option value="${v}" ${form.stars === v ? 'selected' : ''}>${t('stars.' + v)}</option>`).join('')}</select></label>
        <label class="toggle"><input type="checkbox" id="planBrisk" ${form.brisk ? 'checked' : ''}> <span>${t('f.brisk')}</span></label>
      </div></details>
    <div class="wz-foot"><button type="button" class="btn" data-step="1">${t('wz.back')}</button>
      <button type="submit" class="btn primary">${icon('route')} ${t('f.build')}</button></div>
  </form>`;
}
function trailsHtml() {
  return `<div class="list">${G.data.itineraries.map((it) => {
    const x = it.totals;
    return `<div class="card trail" data-trail="${it.id}" ${btn()}>
      <div style="display:flex;justify-content:space-between;gap:8px;align-items:start"><h3>${esc((S.prefs.lang === 'bn' && it.name_bn) || it.name)}</h3><span class="pill">${esc(dn(idx.day[it.day]))} · ${it.start_time}</span></div>
      <p>${esc((S.prefs.lang === 'bn' && it.blurb_bn) || it.blurb)}</p>
      <div class="row"><span>${t('it.pandals', { n: it.pandal_count })}</span>${(() => { const n = it.segments.filter((sg) => sg.type === 'ride').length + hopsIn(it.segments.flatMap((sg) => sg.stops || [])).length; return n ? `<span>🛺 ${t('it.rides', { n })}</span>` : ''; })()}<span>${x.walk_km} km</span><span>${fmt(stepsFor(x.walk_m ?? x.walk_km * 1000))} ${t('kpi.steps')}</span><span>${t('it.dur', { h: Math.floor(x.duration_min / 60), m: x.duration_min % 60 })}</span></div>
    </div>`;
  }).join('')}</div>`;
}
function resultHtml(plan) {
  const x = plan.totals, stops = stopsOf(plan);
  let n = 0, lastFood = -9, hopM = 0; const used = new Set();
  const tl = [`<li class="start"><div class="t">${plan.start}</div><div class="nm">${t('tl.start', { name: esc(ptName(plan.startPt)) })}</div></li>`];
  let prev = ll(plan.startPt);
  for (const s of plan.segments) {
    if (s.type === 'ride') {
      const dest = idx.transit[s.to], opt = dest ? rideOption(prev, ll(dest), G.data.transit, transitData) : { mode: 'cab' };
      tl.push(`<li class="ride"><div class="t">${s.depart}</div><div class="nm">${t('tl.ride', { name: esc(dest?.name || '') })}</div>
        <div class="sub">${rideText(opt, dest?.name || '')} · ${t('tl.rideMin', { n: s.ride_min })}</div></li>`);
      if (dest) prev = ll(dest);
      continue;
    }
    for (const st of s.stops) {
      n++;
      const p = idx.pandal[st.pandal], hour = +st.arrive.slice(0, 2), meal = (hour >= 12 && hour <= 14) || (hour >= 19 && hour <= 21);
      const hop = st.walk_m > HOP_M;
      if (hop) {
        // Too far to walk: say how to ride it. Arrival times stay as planned (walking pace), so riding only buys slack.
        hopM += st.walk_m;
        const opt = rideOption(prev, ll(p), G.data.transit, transitData), kmTxt = km(st.walk_m);
        const mins = Math.round((st.walk_m * 1.3) / (15000 / 60)) + 5;
        tl.push(`<li class="ride hop"><div class="t"></div><div class="nm">${t('tl.hop', { km: kmTxt })}</div>
          <div class="sub">${opt.mode === 'cab' ? t('tl.hopAuto', { name: esc(nm(p)) }) : rideText(opt, nm(p))} · ${t('tl.rideMin', { n: mins })} · ${t('tl.orWalk', { n: st.walk_min })}</div></li>`);
      }
      let eat = '';
      const f = p.food.filter((ff) => ff.distance_m <= 800).map((ff) => idx.food[ff.id]).find((ff) => !used.has(ff.id));
      if (f && (n - lastFood >= 3 || (meal && n - lastFood >= 2))) { used.add(f.id); lastFood = n; eat = `<div class="eat">${t('tl.eat', { dish: esc(f.dishes[0]), place: esc(f.name) })}</div>`; }
      prev = ll(p);
      tl.push(`<li data-n="${n}" data-place="${st.pandal}" ${btn()}><div class="t">${st.arrive}</div><div class="nm">${esc(nm(p))}${visitedToday(st.pandal) ? ' ✓' : ''}</div>
        <div class="sub">${st.walk_m && !hop ? `${t('tl.walk', { m: st.walk_m })} · ` : ''}${crowdWord(st.crowd)} · ${t('tl.inside', { n: st.dwell_min })}</div>${eat}
        <a class="go" target="_blank" rel="noopener" href="${dirUrl(ll(p), hop ? 'transit' : 'walking')}" aria-label="${t('p.directions')}: ${esc(nm(p))}">${icon('pin', 'sm')}</a></li>`);
    }
  }
  // One clear "go" button: directions to the first stop you haven't checked in at yet.
  const next = stops.find((st) => !visitedToday(st.pandal)) || stops[0], np = idx.pandal[next.pandal];
  const walkM = Math.max(0, x.walk_m - hopM);
  return `<div class="card plan-sum">
      <h3>${esc(planTitle(plan))}</h3>
      <div class="fine">${t('plan.sub', { day: dn(idx.day[plan.day]), from: plan.start, to: plan.end, start: esc(ptName(plan.startPt)) })}${plan.skipped ? ` · ${t('plan.dropped', { n: plan.skipped })}` : ''}</div>
      <div class="kpis"><div><b>${x.pandals}</b><span>${t('kpi.pandals')}</span></div><div><b>${km(walkM)}</b><span>${t('kpi.km')}</span></div><div><b>${fmt(stepsFor(walkM))}</b><span>${t('kpi.steps')}</span></div><div><b>${fmt(kcalFor(x.walk_min, x.dwell_min, x.brisk))}</b><span>${t('kpi.kcal')}</span></div></div>
      <a class="btn primary block" id="planNextDir" target="_blank" rel="noopener" href="${dirUrl(ll(np), next.walk_m > HOP_M ? 'transit' : 'walking')}">${icon('pin')} ${t('plan.nextDir', { name: esc(nm(np)) })}</a>
      <div class="btn-row" style="margin-top:8px"><button class="btn" id="planWalk">${icon('walk')} ${t('plan.startWalk')}</button><button class="btn" id="planShare">${icon('share')} ${t('plan.share')}</button></div>
      <p class="fine" style="margin:8px 0 0">${t('plan.dirHint')}</p>
    </div>
    <ol class="timeline">${tl.join('')}</ol>`;
}
function stepperHtml(plan) {
  const labels = [t('wz.s1'), t('wz.s2'), t('wz.s3')];
  const can = (n) => n === 1 || (n === 2 && planSel.size > 0) || (n === 3 && !!plan);
  return `<ol class="stepper">${labels.map((l, i) => {
    const n = i + 1;
    return `<li><button type="button" data-step="${n}" ${n === step ? 'aria-current="step"' : ''} ${can(n) ? '' : 'disabled'} class="${n < step ? 'done' : ''}"><b>${n < step ? '✓' : n}</b>${l}</button></li>`;
  }).join('')}</ol>`;
}
function render(scrollToResult = false) {
  const el = $('#view-plan'), plan = planValid(S.plan) ? S.plan : null;
  if (!step || (step === 3 && !plan)) step = plan ? 3 : 1;
  if (step === 2 && !planSel.size) step = 1;
  if (plan && step === 3 && !transitData) loadTransit();
  const body = step === 1 ? areasHtml() : step === 2 ? formHtml()
    : `<div class="wz-foot top"><button type="button" class="btn sm" id="planEdit">${t(plan.kind === 'custom' ? 'wz.edit' : 'wz.other')}</button><button type="button" class="btn sm" id="planNew">${icon('plus', 'sm')} ${t('wz.new')}</button></div>
       <div id="planResult">${resultHtml(plan)}</div>`;
  el.innerHTML = `<div class="view-title"><h2>${t('plan.title')}</h2><p>${t('plan.subtitle')}</p></div>${stepperHtml(plan)}${body}`;
  wire(el, plan);
  if (scrollToResult || step !== 3) window.scrollTo({ top: 0 });
}
const keepScroll = (fn) => { const y = window.scrollY; fn(); window.scrollTo(0, y); };
function wire(el, plan) {
  el.onclick = (e) => {
    const sp = e.target.closest('[data-step]:not([disabled])')?.dataset.step; if (sp) { step = +sp; return render(); }
    const pr = e.target.closest('[data-pr]')?.dataset.pr;
    if (pr) { const ids = idx.region[pr].zone_ids, on = ids.some((id) => planSel.has(id)); ids.forEach((id) => (on ? planSel.delete(id) : planSel.add(id))); return keepScroll(render); }
    if (e.target.closest('#planNext')) { if (!planSel.size) return toast(t('plan.pickZone')); step = 2; return render(); }
    if (e.target.closest('#planEdit')) { step = plan?.kind === 'custom' ? 2 : 1; return render(); }
    if (e.target.closest('#planNew')) { planSel = new Set(); step = 1; return render(); }
    if (e.target.closest('#planStartBtn')) return startPickerSheet(form.start, (v) => { form.start = v; keepScroll(render); });
    const dp = e.target.closest('[data-dayplan]')?.dataset.dayplan; if (dp) return openDayPlan(+dp);
    const tr = e.target.closest('[data-trail]')?.dataset.trail; if (tr) return showTrail(tr);
    if (e.target.closest('a')) return; // direction links open Google Maps
    const pl = e.target.closest('[data-place]')?.dataset.place; if (pl) return openPlace(pl);
    if (e.target.closest('#planWalk')) { go('me'); if (!walking()) startWalk(); return; }
    if (e.target.closest('#planShare')) return share(plan);
  };
  const f = $('#planForm', el);
  if (f) {
    f.onchange = (ev) => {
      // Whole day starts in the morning, whole night in the evening.
      if (ev?.target?.id === 'planBudget') {
        const b = $('#planBudget').value, h = +($('#planTime').value || '17:00').slice(0, 2);
        if (b === '720' && h >= 13) $('#planTime').value = '10:00';
        if (b === '600' && h < 16) $('#planTime').value = '19:00';
      }
      S.day = $('#planDay').value; form.time = $('#planTime').value || '17:00'; form.stars = $('#planStars').value; form.budget = $('#planBudget').value; form.brisk = $('#planBrisk').checked; };
    f.onsubmit = (e) => { e.preventDefault(); f.onchange(); buildCustom(); };
  }
}

// Opening the tab starts at Areas; re-renders while you're here (e.g. a language switch) keep your step.
registerView('plan', { render: () => { if (!inPlan) step = 1; render(false); } });
addEventListener('viewchange', (e) => { inPlan = e.detail === 'plan'; });
