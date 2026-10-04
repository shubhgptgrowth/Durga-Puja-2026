/* The "people here now" strip on Home. Real numbers only: people active on the site in the last 5 minutes
 * (presence from analytics.js heartbeats) and everyone who has ever opened it (app_opens). Each part is
 * hidden until it is big enough to be worth showing, so nothing small or made-up is displayed. */
import { t, community, loc } from './state.js';
import { onLive, enabled } from './analytics.js';

const LIVE_MIN = 20, PEOPLE_MIN = 500;
let live = null, people = null, today = null, shownLive = 0, started = false;
const subs = new Set();
/** Real counts for the header: { live, today, people } (null until the server answers). */
export const counts = () => ({ live, today, people });
export const onCounts = (fn) => { subs.add(fn); return () => subs.delete(fn); };

const fmt = (n) => Math.round(n).toLocaleString(loc());
const peopleText = (n) => (n >= 1000 ? `${fmt(Math.floor(n / 100) * 100)}+` : fmt(n));

export function liveHtml() {
  // The live count lives in the header pill now; the Home strip keeps the all-time line.
  const showLive = false, showPeople = people != null && people >= PEOPLE_MIN;
  if (!showLive && !showPeople) return '<div id="liveStrip" class="live-strip" hidden></div>';
  if (showLive) shownLive ||= live;
  return `<div id="liveStrip" class="live-strip" aria-live="polite">
    ${showLive ? `<span class="live-now"><span class="live-dot" aria-hidden="true"></span><span>${t('lv.now', { n: `<b id="liveN">${fmt(shownLive)}</b>` })}</span></span>` : ''}
    ${showPeople ? `<span class="live-total">${t('lv.total', { n: `<b>${peopleText(people)}</b>` })}</span>` : ''}</div>`;
}

function tween(to) {
  const el = document.getElementById('liveN');
  if (!el) { shownLive = to; return; }
  const from = shownLive, t0 = performance.now(), dur = 1200;
  const step = (now) => {
    const k = Math.min(1, (now - t0) / dur), v = from + (to - from) * (1 - (1 - k) ** 3);
    el.textContent = fmt(v); shownLive = v;
    if (k < 1) requestAnimationFrame(step); else shownLive = to;
  };
  requestAnimationFrame(step);
}

/* Header pill: the real number of people on the app in the last 5 minutes. */
// Real numbers only. Below PILL_LIVE_MIN people online, the pill shows "Live" with the (real) all-time count instead.
const PILL_LIVE_MIN = 50;
function paintHeader() {
  const pill = document.getElementById('livePill');
  if (!pill) return;
  if (live == null) { pill.hidden = true; return; }
  pill.hidden = false;
  const big = live >= PILL_LIVE_MIN, allTime = people >= PEOPLE_MIN;
  document.getElementById('livePillN').textContent = big ? fmt(live) : t('lv.liveWord');
  document.getElementById('livePillL').textContent = big ? t('lv.pill') : allTime ? t('lv.pillAll', { n: peopleText(people) }) : t('lv.pillSoon');
  pill.setAttribute('aria-label', big ? t('lv.now', { n: fmt(live) }).replace(/<[^>]+>/g, '') : t('lv.liveWord'));
}

function paint() {
  paintHeader(); subs.forEach((fn) => fn(counts()));
  const strip = document.getElementById('liveStrip');
  if (!strip) return;
  const wasLive = !!document.getElementById('liveN');
  const target = live;
  if (wasLive && live >= LIVE_MIN) return tween(target);
  strip.outerHTML = liveHtml();
}

async function refresh() {
  try { const c = await community.siteCounts(); if (c) { live = c.live; people = c.people; today = c.today ?? today; paint(); } } catch { /* offline */ }
}

export function startLiveCount() {
  if (started || !community.enabled) return;
  started = true;
  if (enabled()) onLive((n) => { live = n; paint(); });
  refresh();
  setInterval(() => { if (document.visibilityState === 'visible') refresh(); }, 2 * 60e3);
  document.getElementById('livePill')?.addEventListener('click', () => document.querySelector('.tab[data-view="home"]')?.click());
}
