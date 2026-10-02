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
  constructor({ threshold = 1.1, minGap = 280, maxGap = 2000, streak = 4 } = {}) {
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
export function routeUrls(points) {
  const legs = [];
  for (let i = 0; i < points.length - 1; i += 4) {
    const seg = points.slice(i, i + 5);
    if (seg.length < 2) break;
    const o = seg[0], d = seg[seg.length - 1], w = seg.slice(1, -1);
    legs.push(`https://www.google.com/maps/dir/?api=1&origin=${o[0]},${o[1]}&destination=${d[0]},${d[1]}`
      + (w.length ? '&waypoints=' + encodeURIComponent(w.map((p) => p.join(',')).join('|')) : '') + '&travelmode=walking');
  }
  return legs;
}

/** "HH:MM-HH:MM" opening hours, including ranges that cross midnight. */
export function isOpen(hours, d = new Date()) {
  const [a, b] = hours.split('-').map((x) => { const [h, m] = x.split(':').map(Number); return h * 60 + m; });
  const now = d.getHours() * 60 + d.getMinutes();
  return a <= b ? now >= a && now <= b : now >= a || now <= b;
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
