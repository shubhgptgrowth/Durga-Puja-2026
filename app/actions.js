/* User actions with side effects: verified visits (check-in or "I ate here"), badges, and the walk tracker. */
import { hav, judgeFix, StepDetector } from './core.js';
import {
  S, G, idx, t, store, community, ll, M, nm, placeOf, placeKind, todayKey, stride, stepsFor,
} from './state.js';
import { toast, getFix, rerender } from './ui.js';

/* ---------------- day records ---------------- */
export function dayRec(key = todayKey()) {
  const r = (S.history[key] ||= { m: 0, ms: 0, pandals: [], foods: [] });
  r.foods ||= []; r.pandals ||= [];
  if (r.steps == null) r.steps = stepsFor(r.m || 0);
  return r;
}
export const saveHistory = () => store.set('history', S.history);
// Steps the user copied from their phone's Health app or watch (r.health) win when higher than what we tracked.
export const daySteps = (r) => Math.max(r.steps != null ? Math.round(r.steps) : stepsFor(r.m || 0), r.health || 0);
export const dayDist = (r) => Math.max(r.m || 0, r.steps != null && !r.m ? r.steps * stride() : 0);
export const dayWalkMin = (r) => Math.max((r.ms || 0) / 60000, (daySteps(r) * stride()) / ((M().walk_kmh_crowd * 1000) / 60));
export const visitedToday = (id) => {
  const r = S.history[todayKey()];
  return !!r && ((r.pandals || []).includes(id) || (r.foods || []).includes(id));
};

/* ---------------- badges ---------------- */
export const BADGES = [
  { id: 'first', em: '🪔', name: 'Prothom Darshan', bn: 'প্রথম দর্শন' },
  { id: 'five', em: '🖐️', name: 'Panch Pandal', bn: 'পাঁচ প্যান্ডেল' },
  { id: 'fifteen', em: '🥁', name: 'Dhaki', bn: 'ঢাকি' },
  { id: 'thirty', em: '👑', name: 'Pujo Legend', bn: 'পুজো কিংবদন্তি' },
  { id: 'zone', em: '🗺️', name: 'Zone Master', bn: 'অঞ্চল-জয়ী' },
  { id: 'k10', em: '🏃', name: '10K Pujo', bn: '১০ কিমি পুজো' },
  { id: 'ashtami', em: '🔥', name: 'Ashtami Marathon', bn: 'অষ্টমী ম্যারাথন' },
  { id: 'dawn', em: '🌅', name: 'Bhor-er Pakhi', bn: 'ভোরের পাখি' },
  { id: 'owl', em: '🦉', name: 'Raat Jaga', bn: 'রাত জাগা' },
  { id: 'foodie', em: '😋', name: 'Pet Pujo', bn: 'পেটপুজো' },
  { id: 'ns', em: '🧭', name: 'Uttor–Dokkhin', bn: 'উত্তর–দক্ষিণ' },
  { id: 'goal', em: '🎯', name: 'Goal Getter', bn: 'লক্ষ্যভেদ' },
  { id: 'lens', em: '📸', name: 'Pujo Lens', bn: 'পুজোর লেন্স' },
];
export function earned() {
  const n = Object.keys(S.checkins).length, got = new Set();
  if (n >= 1) got.add('first'); if (n >= 5) got.add('five'); if (n >= 15) got.add('fifteen'); if (n >= 30) got.add('thirty');
  if (G.data.zones.some((z) => z.pandal_ids.every((id) => S.checkins[id]))) got.add('zone');
  const hours = Object.values(S.checkins).map((c) => new Date(c.ts).getHours());
  if (hours.some((h) => h >= 4 && h < 7)) got.add('dawn');
  if (hours.some((h) => h >= 0 && h < 4)) got.add('owl');
  if (new Set(Object.values(S.history).flatMap((d) => d.foods || [])).size >= 3) got.add('foodie');
  if (store.get('myMoments', 0) >= 3) got.add('lens');
  for (const [date, d] of Object.entries(S.history)) {
    if (dayDist(d) >= 10000) got.add('k10');
    if (date === idx.day.ashtami.date && daySteps(d) >= 20000) got.add('ashtami');
    if (daySteps(d) >= S.prefs.goal) got.add('goal');
    const zset = new Set((d.pandals || []).map((id) => idx.pandal[id]?.zone));
    if (zset.has('north') && (zset.has('south_gariahat') || zset.has('south_lakemarket') || zset.has('southwest'))) got.add('ns');
  }
  return got;
}
export function announceBadges(before) {
  const now = earned();
  // celebrate.js shows each new badge with an animation (after any check-in celebration).
  for (const b of BADGES) if (now.has(b.id) && !before.has(b.id)) document.dispatchEvent(new CustomEvent('pp:badge', { detail: b }));
}

/* ---------------- visits ---------------- */
function markLocal(id, how) {
  const before = earned();
  const kind = placeKind(id), rec = dayRec();
  if (kind === 'pandal') {
    if (!S.checkins[id]) S.checkins[id] = { ts: Date.now(), how };
    store.set('checkins', S.checkins);
    if (!rec.pandals.includes(id)) rec.pandals.push(id);
  } else if (!rec.foods.includes(id)) rec.foods.push(id);
  saveHistory();
  if (navigator.vibrate) navigator.vibrate(40);
  announceBadges(before);
}

/** How close (m) you must be for a visit to count. This mirrors the server rule in supabase/migrations. */
export const allowedDistance = (p, accuracy) => (p.checkin_radius_m || 350) + Math.min(Math.max(accuracy ?? 50, 0), 100);

/**
 * Verify that you're at the place, then record the visit locally and in the community count.
 * Returns {status: 'counted'|'duplicate'|'queued'|'local'|'too_far'|'denied'|'no_fix', distance?, today?}.
 */
export async function visit(id, { fix = null } = {}) {
  const p = placeOf(id);
  let f = fix;
  // Always a fresh fix: a cached one could be from before you walked up to the place.
  if (!f) { try { f = await getFix({ maximumAge: 0 }); } catch (e) { return { status: e.code === 'denied' ? 'denied' : 'no_fix' }; } }
  const d = hav([f.lat, f.lng], ll(p));
  if (d > allowedDistance(p, f.accuracy)) return { status: 'too_far', distance: d };
  markLocal(id, fix ? 'gps' : 'tap');
  if (!community.enabled) return { status: 'local', distance: d };
  try { return { ...(await community.recordVisit(id, f)), distance: d }; } catch { return { status: 'queued', distance: d }; }
}
/** Tell the page a visit went through, so celebrate.js can throw petals. Not for duplicates or private marks. */
export function celebrateVisit(id, r) {
  if (['counted', 'local', 'queued'].includes(r.status)) document.dispatchEvent(new CustomEvent('pp:visit', { detail: { id, kind: placeKind(id) } }));
}
/** "Visited, but only on my phone": used when GPS can't confirm. Never counted publicly. */
export const visitPrivately = (id) => markLocal(id, 'manual');

/** Toast text for a visit result. */
export function visitMessage(id, r) {
  const p = placeOf(id), name = nm(p), food = placeKind(id) === 'food';
  switch (r.status) {
    case 'counted': return t(food ? 'v.ateCounted' : 'v.counted', { name, n: r.today });
    case 'duplicate': return t('v.duplicate', { name });
    case 'queued': return t('v.queued', { name });
    case 'local': return t(food ? 'v.ateLocal' : 'v.local', { name });
    case 'too_far': return t('v.tooFar', { d: r.distance < 1000 ? `${Math.round(r.distance)} m` : `${(r.distance / 1000).toFixed(1)} km` });
    case 'denied': return t('fit.denied');
    case 'rate_limited': return t('v.rate');
    default: return t('v.noFix');
  }
}

/* ---------------- walk tracker ---------------- */
let watchId = null, wakeLock = null, detector = null, lastMotion = 0, motionSaveT = 0, motionRenderT = 0;
export const motionLive = () => Date.now() - lastMotion < 3000;
export const walking = () => !!S.walk;

export async function startWalk() {
  if (!navigator.geolocation) return toast(t('fit.noGps'));
  // iOS only grants motion access inside a user gesture, so ask before anything else is awaited.
  let motion = 'off';
  if (S.prefs.motion && window.DeviceMotionEvent) {
    try {
      if (typeof DeviceMotionEvent.requestPermission === 'function') {
        motion = (await DeviceMotionEvent.requestPermission()) === 'granted' ? 'on' : 'denied';
        if (motion === 'on') attachMotion();
      } else { attachMotion(); motion = 'on'; }
    } catch { motion = 'denied'; /* fall back to GPS steps */ }
  }
  S.walk = { last: null, startedAt: Date.now(), status: motion === 'denied' ? t('fit.motionDenied') : '' };
  // If the sensor never reports (blocked in browser settings, or no sensor), say so: steps then come from GPS distance.
  if (motion === 'on') setTimeout(() => { if (S.walk && !lastMotion) { S.walk.status = t('fit.noMotion'); rerender(); } }, 5000);
  store.set('walking', true);
  watchId = navigator.geolocation.watchPosition(onPos, (err) => { S.walk && (S.walk.status = err.code === 1 ? t('fit.denied') : t('fit.waiting')); rerender(); },
    { enableHighAccuracy: true, maximumAge: 3000, timeout: 30000 });
  try { wakeLock = await navigator.wakeLock?.request('screen'); } catch { /* not supported */ }
  rerender();
}
export function stopWalk() {
  if (watchId != null) navigator.geolocation.clearWatch(watchId);
  removeEventListener('devicemotion', onMotion);
  watchId = null; S.walk = null; detector = null; store.set('walking', false);
  try { wakeLock?.release(); } catch { /* ignore */ } wakeLock = null;
  saveHistory(); toast(t('fit.saved')); rerender();
}
document.addEventListener('visibilitychange', async () => {
  if (document.visibilityState === 'visible' && S.walk && !wakeLock) { try { wakeLock = await navigator.wakeLock?.request('screen'); } catch { /* ignore */ } }
  if (document.visibilityState === 'hidden') saveHistory();
});

function attachMotion() { detector = new StepDetector(); addEventListener('devicemotion', onMotion); }
function onMotion(e) {
  const a = e.accelerationIncludingGravity;
  if (!S.walk || !detector || !a || a.x == null) return;
  lastMotion = Date.now();
  const added = detector.push(a.x, a.y, a.z, e.timeStamp || performance.now());
  if (!added) return;
  dayRec().steps += added;
  const now = Date.now();
  if (now - motionSaveT > 10000) { motionSaveT = now; saveHistory(); }
  if (now - motionRenderT > 1000 && S.view === 'me') { motionRenderT = now; rerender(); }
}

/* GPS fixes: noisy ones and vehicle-speed ones are discarded (see core.judgeFix). */
function onPos(pos) {
  const { latitude: lat, longitude: lng, accuracy } = pos.coords;
  S.me = [lat, lng];
  const w = S.walk; if (!w) return;
  const fix = { lat, lng, accuracy, t: pos.timestamp || Date.now() };
  const v = judgeFix(w.last, fix);
  if (v.reason === 'inaccurate') { w.status = t('fit.weak', { m: Math.round(accuracy) }); if (S.view === 'me') rerender(); return; }
  w.status = '';
  if (v.use) {
    const rec = dayRec(); rec.m += v.dist; rec.ms += v.dt * 1000;
    if (!motionLive()) rec.steps += v.dist / stride(); // without a live motion sensor, estimate steps from distance
    saveHistory();
  }
  if (v.keep) w.last = fix;
  // Auto check-in: walking right up to a pandal counts as a verified visit.
  for (const pd of G.data.pandals) {
    if (!S.checkins[pd.id] && !visitedToday(pd.id) && hav([lat, lng], ll(pd)) <= M().checkin_radius_m) {
      visit(pd.id, { fix }).then((r) => { toast(visitMessage(pd.id, r)); celebrateVisit(pd.id, r); rerender(); });
    }
  }
  document.dispatchEvent(new CustomEvent('pp:position', { detail: fix }));
  if (S.view === 'me') rerender();
}
