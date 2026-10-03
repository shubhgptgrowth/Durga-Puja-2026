/* Usage analytics: which pages, places, sounds and buttons people use, plus the live "here now" count.
 * Anonymous: the same random device id as the reach count (growth.js), no sign-in, no location, no name.
 * Events are batched and sent with a heartbeat every 60 s while the page is visible (one small request),
 * and flushed when the page is hidden. Browsers asking not to be tracked (Do Not Track / Global Privacy
 * Control) send nothing. The team reads the results in Supabase (schema "analytics"), see
 * docs/product/ANALYTICS.md. */
import { S, community } from './state.js';
import { deviceId } from './growth.js';

const BEAT_MS = 60e3, MAX_QUEUE = 200;
let queue = [], timer = null, live = null;
const listeners = new Set();
const optedOut = () => navigator.doNotTrack === '1' || navigator.globalPrivacyControl === true || window.doNotTrack === '1';
export const enabled = () => community.enabled && !optedOut();

/** Record an event. name: view, place_open, directions, transit, checkin, rate, share, sfx, music, filter, lang, plan, trail, moment. */
export function track(name, { place = null, kind = null, d = null } = {}) {
  if (!enabled()) return;
  queue.push({ n: name, view: S.view, place, kind, d: d == null ? null : String(d).slice(0, 60), t: Date.now() });
  if (queue.length > MAX_QUEUE) queue = queue.slice(-MAX_QUEUE);
  if (queue.length >= 25) flush();
}

/** A place page opened. Re-renders of the same open page (day chips, photos) don't count again. */
let cur = { place: null, kind: null };
export function placeOpened(place, kind) {
  if (cur.place === place && document.querySelector('#sheet.open')) return;
  cur = { place, kind };
  track('place_open', { place, kind });
}

export async function flush({ keepalive = false } = {}) {
  if (!enabled() || !navigator.onLine) return;
  const batch = queue.splice(0, 50);
  try {
    const r = await community.track(deviceId(), batch, { keepalive });
    if (r?.live != null) { live = r.live; listeners.forEach((fn) => fn(live)); }
  } catch { queue = batch.concat(queue).slice(-MAX_QUEUE); } // keep them for the next beat
}

/** Live count of people active in the last 5 minutes (real, from the server); null until known. */
export const liveNow = () => live;
export const onLive = (fn) => { listeners.add(fn); return () => listeners.delete(fn); };

export function startAnalytics() {
  if (!enabled()) return;
  const beat = () => { if (document.visibilityState === 'visible') flush(); };
  track('view', { d: S.view });
  addEventListener('viewchange', (e) => track('view', { d: e.detail }));
  setTimeout(beat, 2500);
  timer = setInterval(beat, BEAT_MS);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flush({ keepalive: true });
    else beat();
  });
  addEventListener('online', beat);
  community.on((type, x) => { if (type === 'moment') track('moment', { place: x.placeId, d: x.mediaType }); });
  // Taps on outbound links: directions and public-transport routes, tied to the place sheet that is open.
  document.addEventListener('click', (e) => {
    const a = e.target.closest('a[href]'); if (!a) return;
    const href = a.getAttribute('href') || '';
    const { place, kind } = document.querySelector('#sheet.open') ? cur : { place: null, kind: null };
    if (/google\.com\/maps\/dir/.test(href)) track(/travelmode=transit/.test(href) ? 'transit' : 'directions', { place, kind });
    else if (/wa\.me\//.test(href)) track('share', { place, kind, d: 'whatsapp' });
    else if (/music\.youtube\.com|open\.spotify\.com/.test(href)) track('music', { d: 'open:' + new URL(href, location.href).hostname });
  }, true);
}
export const stopAnalytics = () => clearInterval(timer);
