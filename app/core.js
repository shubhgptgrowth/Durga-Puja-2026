/* Pure, DOM-free logic shared by the app and the JS tests.
 * The geometry, crowd and fitness maths mirror pipeline/geo.py, enrich.py and fitness.py. */

const R = 6371000;
const rad = (d) => (d * Math.PI) / 180;

export function hav(a, b) {
  const [la1, ln1] = a, [la2, ln2] = b;
  const h = Math.sin(rad(la2 - la1) / 2) ** 2 + Math.cos(rad(la1)) * Math.cos(rad(la2)) * Math.sin(rad(ln2 - ln1) / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

export const pathLen = (pts, detour = 1) => pts.slice(1).reduce((s, p, i) => s + hav(pts[i], p) * detour, 0);

/** Nearest-neighbour seed + 2-opt. `start` is fixed; returns a permutation of indices into `stops`. */
export function orderRoute(start, stops) {
  const n = stops.length;
  if (n <= 1) return [...Array(n).keys()];
  const rem = new Set(stops.keys());
  let cur = start, order = [];
  while (rem.size) {
    let best = null, bd = Infinity;
    for (const i of rem) { const d = hav(cur, stops[i]); if (d < bd) { bd = d; best = i; } }
    order.push(best); rem.delete(best); cur = stops[best];
  }
  const len = (o) => pathLen([start, ...o.map((i) => stops[i])]);
  let bestLen = len(order), improved = true;
  while (improved) {
    improved = false;
    for (let i = 0; i < n - 1; i++) for (let j = i + 1; j < n; j++) {
      const c = [...order.slice(0, i), ...order.slice(i, j + 1).reverse(), ...order.slice(j + 1)];
      const cl = len(c);
      if (cl < bestLen - 1e-6) { order = c; bestLen = cl; improved = true; }
    }
  }
  return order;
}

export const crowdIndex = (hourFactors, base, dayFactor, hour) =>
  Math.min(100, Math.round((base / 5) * dayFactor * hourFactors[((hour % 24) + 24) % 24] * 100));

export const strideM = (heightCm, strideFactor = 0.415) => (heightCm / 100) * strideFactor;
export const stepsFor = (m, heightCm, strideFactor) => Math.round(m / strideM(heightCm, strideFactor));
export const kcalFor = ({ walkMin, queueMin = 0, weightKg, met, queueMet = 1.5 }) =>
  Math.round((met * weightKg * walkMin) / 60 + (queueMet * weightKg * queueMin) / 60);

/** Decide whether a GPS fix counts as walking.
 *  Returns {use, dist, dt, reason}. `use` is true only for a credible walking movement. */
export function judgeFix(last, fix, { maxAccuracy = 35, minMove = 3, maxKmh = 10 } = {}) {
  if (fix.accuracy > maxAccuracy) return { use: false, reason: 'inaccurate' };
  if (!last) return { use: false, reason: 'first', keep: true };
  const dist = hav([last.lat, last.lng], [fix.lat, fix.lng]);
  const dt = (fix.t - last.t) / 1000;
  if (dt <= 0 || dist < minMove) return { use: false, reason: 'jitter' };
  if ((dist / dt) * 3.6 > maxKmh) return { use: false, reason: 'vehicle', keep: true, dist, dt };
  return { use: true, keep: true, dist, dt: Math.min(dt, 120) };
}

/** Accelerometer step detector. Feed it accelerationIncludingGravity samples.
 *  It subtracts gravity with a slow EMA, smooths with a fast EMA, and counts upward
 *  threshold crossings 0.28–2 s apart. Steps only count once a streak of 4 is
 *  reached, so a single shake or a bump in an auto doesn't count. */
export class StepDetector {
  // threshold 0.55 m/s²: a phone carried in the hand bounces only ~0.6–1.2 m/s² per step (1.1 missed most of them).
  constructor({ threshold = 0.55, minGap = 280, maxGap = 2000, streak = 4 } = {}) {
    Object.assign(this, { threshold, minGap, maxGap, streak });
    this.g = null; this.s = 0; this.above = false; this.lastStep = -Infinity; this.pending = 0; this.total = 0;
  }
  /** Returns the number of newly confirmed steps for this sample (often 0). */
  push(x, y, z, t) {
    const mag = Math.sqrt(x * x + y * y + z * z);
    this.g = this.g == null ? mag : this.g + 0.05 * (mag - this.g);
    this.s += 0.35 * (mag - this.g - this.s);
    let added = 0;
    if (!this.above && this.s > this.threshold) {
      this.above = true;
      const gap = t - this.lastStep;
      if (gap >= this.minGap) {
        if (gap > this.maxGap) this.pending = 0;
        this.pending++; this.lastStep = t;
        if (this.pending === this.streak) added = this.streak;
        else if (this.pending > this.streak) added = 1;
      }
    } else if (this.above && this.s < this.threshold * 0.4) {
      this.above = false;
    }
    this.total += added;
    return added;
  }
}

/** Google Maps mobile web allows only 3 waypoints, so routes are split into legs of up to 5 points. */
export function routeUrls(points, travelmode = 'walking') {
  const legs = [];
  for (let i = 0; i < points.length - 1; i += 4) {
    const seg = points.slice(i, i + 5);
    if (seg.length < 2) break;
    const o = seg[0], d = seg[seg.length - 1], w = seg.slice(1, -1);
    legs.push(`https://www.google.com/maps/dir/?api=1&origin=${o[0]},${o[1]}&destination=${d[0]},${d[1]}`
      + (w.length ? '&waypoints=' + encodeURIComponent(w.map((p) => p.join(',')).join('|')) : '') + '&travelmode=' + travelmode);
  }
  return legs;
}

/** "HH:MM-HH:MM" opening hours, including ranges that cross midnight. */
export function isOpen(hours, d = new Date()) {
  if (!/^\d{1,2}:\d{2}-\d{1,2}:\d{2}$/.test(hours || '')) return false; // unknown hours (OSM rows often have none)
  const [a, b] = hours.split('-').map((x) => { const [h, m] = x.split(':').map(Number); return h * 60 + m; });
  const now = d.getHours() * 60 + d.getMinutes();
  return a <= b ? now >= a && now <= b : now >= a || now <= b;
}

/** Opening and closing minutes for "HH:MM-HH:MM", or null when the hours aren't known. */
export function hoursOf(hours) {
  if (!/^\d{1,2}:\d{2}-\d{1,2}:\d{2}$/.test(hours || '')) return null;
  const [open, close] = hours.split('-').map((x) => { const [h, m] = x.split(':').map(Number); return h * 60 + m; });
  return { open, close };
}

export const hhmm = (min) => {
  min = ((Math.round(min) % 1440) + 1440) % 1440;
  return `${String(Math.floor(min / 60)).padStart(2, '0')}:${String(min % 60).padStart(2, '0')}`;
};

/* Shareable plan links: #plan=<base64url(JSON)> */
const b64u = (s) => btoa(unescape(encodeURIComponent(s))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const unb64u = (s) => decodeURIComponent(escape(atob(s.replace(/-/g, '+').replace(/_/g, '/'))));
export const encodePlan = (p) => b64u(JSON.stringify(p));
export function decodePlan(s) {
  try {
    const p = JSON.parse(unb64u(s));
    if (!Array.isArray(p.z) || !p.z.length || typeof p.s !== 'string') return null;
    return p;
  } catch { return null; }
}

/* Compact counts for badges: 950 → "950", 1234 → "1.2k", 25300 → "25k". */
export function fmtCount(n) {
  n = Math.max(0, Math.round(n || 0));
  if (n < 1000) return String(n);
  if (n < 10000) return (Math.floor(n / 100) / 10).toFixed(1).replace(/\.0$/, '') + 'k';
  if (n < 1e6) return Math.floor(n / 1000) + 'k';
  return (Math.floor(n / 1e5) / 10).toFixed(1).replace(/\.0$/, '') + 'M';
}

/* "just now" / "5m" / "3h" / "2d" relative age. */
export function timeAgo(iso, now = Date.now()) {
  const s = Math.max(0, (now - new Date(iso).getTime()) / 1000);
  if (s < 60) return { n: 0, unit: 'now' };
  if (s < 3600) return { n: Math.floor(s / 60), unit: 'm' };
  if (s < 86400) return { n: Math.floor(s / 3600), unit: 'h' };
  return { n: Math.floor(s / 86400), unit: 'd' };
}

/* Simple, forgiving search over {id, kind, names: [..], extra: [..]} entries.
 * Ranking: exact or prefix match on a name word, then a substring in a name, then a substring in the extras. */
export function searchEntries(entries, query, limit = 8) {
  const q = query.trim().toLowerCase();
  if (q.length < 2) return [];
  const scored = [];
  for (const e of entries) {
    let best = 0;
    for (const n of e.names) {
      const s = n.toLowerCase();
      if (s === q) best = Math.max(best, 100);
      else if (s.startsWith(q)) best = Math.max(best, 80);
      else if (s.split(/[\s,()-]+/).some((w) => w.startsWith(q))) best = Math.max(best, 60);
      else if (s.includes(q)) best = Math.max(best, 40);
    }
    if (!best) for (const x of e.extra || []) if (x.toLowerCase().includes(q)) { best = 20; break; }
    if (best) scored.push([best + (e.boost || 0), e]);
  }
  return scored.sort((a, b) => b[0] - a[0]).slice(0, limit).map(([, e]) => e);
}

/* The nearest places to a point, within `maxM`. */
export function nearest(point, places, { maxM = Infinity, limit = 5 } = {}) {
  return places.map((p) => [p, hav(point, [p.lat, p.lng])]).filter(([, d]) => d <= maxM)
    .sort((a, b) => a[1] - b[1]).slice(0, limit).map(([p, d]) => ({ place: p, distance: d }));
}

/* ---------------- ride legs: metro, bus, auto or cab ---------------- */
function stopsNear(pt, stops, maxM) {
  const out = [], dLat = maxM / 111000, dLng = maxM / 103000;
  for (let i = 0; i < stops.length; i++) {
    const s = stops[i];
    if (Math.abs(s[0] - pt[0]) > dLat || Math.abs(s[1] - pt[1]) > dLng) continue;
    const d = hav(pt, [s[0], s[1]]);
    if (d <= maxM) out.push([i, d]);
  }
  return out.sort((a, b) => a[1] - b[1]);
}
function segDist(p, a, b) {
  const k = Math.cos((p[0] * Math.PI) / 180) * 111320;
  const P = [p[1] * k, p[0] * 110540], A = [a[1] * k, a[0] * 110540], B = [b[1] * k, b[0] * 110540];
  const dx = B[0] - A[0], dy = B[1] - A[1];
  const t = Math.max(0, Math.min(1, ((P[0] - A[0]) * dx + (P[1] - A[1]) * dy) / (dx * dx + dy * dy || 1)));
  return Math.hypot(P[0] - A[0] - t * dx, P[1] - A[1] - t * dy);
}

/**
 * Best way to ride from `from` to `to` ([lat, lng]). `stations` are metro/rail stations
 * {id, name, line, lat, lng}; `transit` is app/data/transit.json (optional).
 * Returns {mode:'metro', line, board, alight} | {mode:'bus'|'auto', routes, board, alight} | {mode:'auto', route, via} | {mode:'cab'}.
 */
/** How to ride from one point to another. `prefer` is how the visitor is travelling: 'any' (best available:
 * metro, then bus, then shared auto, then cab), 'metro', 'bus' or 'auto' (that mode when it serves the hop, else the
 * best available, marked fallback), 'car' (drive) or 'walk' (no ride). */
export function rideOption(from, to, stations, transit = null, prefer = 'any') {
  if (prefer === 'walk') return { mode: 'walk' };
  if (prefer === 'car') return { mode: 'car' };
  const opts = {};
  const nearestStation = (pt) => stations.filter((s) => s.line !== 'suburban').map((s) => [s, hav(pt, [s.lat, s.lng])]).sort((a, b) => a[1] - b[1])[0];
  const a = nearestStation(from), b = nearestStation(to);
  if (a && b && a[0].id !== b[0].id && a[1] <= 1000 && b[1] <= 1000 && a[0].line === b[0].line) {
    opts.metro = { mode: 'metro', line: a[0].line, board: a[0].name, alight: b[0].name };
  }
  if (transit) {
    const fs = stopsNear(from, transit.stops, 500), ts = stopsNear(to, transit.stops, 500);
    if (fs.length && ts.length) {
      const fset = new Map(fs.map(([i, d]) => [i, d])), tset = new Map(ts.map(([i, d]) => [i, d]));
      for (const mode of ['bus', 'auto']) {
        const hits = [];
        for (const r of transit.routes) {
          if (r.m !== mode) continue;
          let bi = -1, best = null;
          r.s.forEach((sid, k) => { if (fset.has(sid) && bi < 0) bi = k; if (bi >= 0 && k > bi && tset.has(sid) && !best) best = [r.s[bi], sid]; });
          if (best) hits.push({ label: r.l, board: best[0], alight: best[1], walk: fset.get(best[0]) + tset.get(best[1]) });
        }
        if (hits.length) {
          hits.sort((x, y) => x.walk - y.walk);
          const labels = [...new Set(hits.map((h) => h.label))].slice(0, 4);
          opts[mode] = { mode, routes: labels, board: transit.stops[hits[0].board][2] || '', alight: transit.stops[hits[0].alight][2] || '' };
        }
      }
    }
    if (!opts.auto) {
      const auto = (transit.autos || []).map((x) => [x, segDist(from, x.a, x.b) + segDist(to, x.a, x.b)])
        .filter(([x]) => segDist(from, x.a, x.b) <= 700 && segDist(to, x.a, x.b) <= 700).sort((p, q) => p[1] - q[1])[0];
      if (auto) opts.auto = { mode: 'auto', route: auto[0].l, via: auto[0].via };
    }
  }
  if (prefer !== 'any' && opts[prefer]) return opts[prefer];
  const best = opts.metro || opts.bus || opts.auto || { mode: 'cab' };
  return prefer === 'any' ? best : { ...best, fallback: prefer };
}

/** iPhone Shortcut sync: the Shortcut opens …#steps=8432 (optionally &date=2026-10-18) with Apple Health's step total.
 * Shortcuts may format the number ("8,432", "8432.0"), so separators are dropped and the value rounded. */
export function parseSteps(s, today) {
  const [raw, ...rest] = decodeURIComponent(s).split('&');
  const n = Math.round(parseFloat(raw.replace(/[^\d.]/g, '')));
  const date = new URLSearchParams(rest.join('&')).get('date');
  if (!Number.isFinite(n) || n < 0) return null;
  return { n: Math.min(n, 100000), date: /^\d{4}-\d{2}-\d{2}$/.test(date || '') && date <= today ? date : today };
}

/** Merge two copies of My Pujo progress (this browser's and the backup) so neither loses anything:
 * per day the larger distance, time and step counts, and the union of pandals and food stops; check-ins
 * keep the earliest; counters take the larger; the name and goal come from `a` when set. */
export function mergeProgress(a = {}, b = {}) {
  const days = {}, ha = a.history || {}, hb = b.history || {};
  for (const d of new Set([...Object.keys(ha), ...Object.keys(hb)])) {
    const x = ha[d] || {}, y = hb[d] || {};
    days[d] = {
      m: Math.max(x.m || 0, y.m || 0), ms: Math.max(x.ms || 0, y.ms || 0),
      steps: Math.max(x.steps || 0, y.steps || 0), health: Math.max(x.health || 0, y.health || 0) || undefined,
      pandals: [...new Set([...(x.pandals || []), ...(y.pandals || [])])], foods: [...new Set([...(x.foods || []), ...(y.foods || [])])],
    };
    if (!days[d].health) delete days[d].health;
  }
  const checkins = { ...(b.checkins || {}) };
  for (const [id, c] of Object.entries(a.checkins || {})) if (!checkins[id] || c.ts < checkins[id].ts) checkins[id] = c;
  return {
    v: 1, history: days, checkins,
    name: a.name || b.name || '', goal: a.goal || b.goal, height: a.height || b.height, weight: a.weight || b.weight,
    myMoments: Math.max(a.myMoments || 0, b.myMoments || 0), myRatings: { ...(b.myRatings || {}), ...(a.myRatings || {}) },
  };
}
