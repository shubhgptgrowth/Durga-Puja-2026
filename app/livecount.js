/* The "people here now" strip on Home. Real numbers only: people active on the site in the last 5 minutes
 * (presence from analytics.js heartbeats) and everyone who has ever opened it (app_opens). Each part is
 * hidden until it is big enough to be worth showing, so nothing small or made-up is displayed. */
import { t, community, loc } from './state.js';
import { onLive, enabled } from './analytics.js';

const LIVE_MIN = 20, PEOPLE_MIN = 500;
let live = null, people = null, shownLive = 0, started = false;

const fmt = (n) => Math.round(n).toLocaleString(loc());
const peopleText = (n) => (n >= 1000 ? `${fmt(Math.floor(n / 100) * 100)}+` : fmt(n));

export function liveHtml() {
  const showLive = live != null && live >= LIVE_MIN, showPeople = people != null && people >= PEOPLE_MIN;
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

function paint() {
  const strip = document.getElementById('liveStrip');
  if (!strip) return;
  const wasLive = !!document.getElementById('liveN');
  const target = live;
  if (wasLive && live >= LIVE_MIN) return tween(target);
  strip.outerHTML = liveHtml();
}

async function refresh() {
  try { const c = await community.siteCounts(); if (c) { live = c.live; people = c.people; paint(); } } catch { /* offline */ }
}

export function startLiveCount() {
  if (started || !community.enabled) return;
  started = true;
  if (enabled()) onLive((n) => { live = n; paint(); });
  refresh();
  setInterval(() => { if (document.visibilityState === 'visible') refresh(); }, 5 * 60e3);
}
