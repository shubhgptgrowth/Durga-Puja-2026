/* Growth: which link brought someone (?src=), an anonymous once-per-boot open count, deep links to
 * places (#p=<id>), WhatsApp/share buttons, and shareable 1080×1920 story cards for Instagram and
 * WhatsApp Status. See docs/MARKETING.md for the link codes. */
import { S, G, idx, t, store, community, nm, fmt, km, dn, todayKey } from './state.js';
import { toast } from './ui.js';
import { daySteps, dayDist, earned } from './actions.js';

const SRC_RE = /^[a-z0-9_]{1,40}$/;
const BASE = () => location.origin + location.pathname;

/** Read ?src= (or utm_source) once at boot, remember the first one, and tidy the URL. */
export function captureSource() {
  const q = new URLSearchParams(location.search);
  let src = (q.get('src') || q.get('utm_source') || '').trim().toLowerCase();
  if (src && !SRC_RE.test(src)) src = 'other';
  if (src) {
    if (!store.get('firstSrc', null)) store.set('firstSrc', src);
    for (const k of ['src', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'fbclid', 'igshid']) q.delete(k);
    const qs = q.toString();
    history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
  }
  S.src = src || 'direct';
}

function deviceId() {
  let id = store.get('device', null);
  if (!id) { id = crypto.randomUUID?.() || 'xxxxxxxx-xxxx-4xxx-8xxx-xxxxxxxxxxxx'.replace(/x/g, () => ((Math.random() * 16) | 0).toString(16)); store.set('device', id); }
  return id;
}

/** Count this open (anonymous device id, no sign-in). Best effort: retried once when back online. */
export function trackOpen() {
  if (!community.enabled) return;
  const send = () => community.trackOpen(deviceId(), S.src, store.get('firstSrc', S.src))
    .then(() => store.set('lastOpen', todayKey())).catch(() => {});
  if (navigator.onLine) setTimeout(send, 1200);
  else addEventListener('online', send, { once: true });
}

/* ---------------- links and share buttons ---------------- */
export const placeLink = (id, src) => `${BASE()}?src=${src}#p=${id}`;
export const appLink = (src) => `${BASE()}?src=${src}`;
export const waUrl = (text) => `https://wa.me/?text=${encodeURIComponent(text)}`;

function placeText(id) {
  const p = idx.pandal[id] || idx.food[id];
  return t(idx.pandal[id] ? 'g.pandalText' : 'g.foodText', { name: nm(p) });
}

export function shareRowHtml(id) {
  return `<div class="btn-row share-row">
    <a class="btn sm wa" id="waShare" target="_blank" rel="noopener" href="${waUrl(`${placeText(id)}\n${placeLink(id, 'wa_place')}`)}">💬 ${t('g.wa')}</a>
    ${idx.pandal[id] ? `<button class="btn sm" id="storyShare">📸 ${t('g.story')}</button>` : ''}
    <button class="btn sm" id="linkShare">🔗 ${t('g.link')}</button></div>`;
}

export function wireShareRow(el, id) {
  const story = el.querySelector('#storyShare');
  if (story) story.onclick = () => shareCard(placeCard(id), `${placeText(id)}\n${placeLink(id, 'ig_story')}`, `pujo-${id}.png`);
  const link = el.querySelector('#linkShare');
  if (link) link.onclick = () => shareLink(placeText(id), placeLink(id, 'share'));
}

export async function shareLink(text, url) {
  try {
    if (navigator.share) { await navigator.share({ title: 'Pujo Parikrama', text, url }); return; }
    await navigator.clipboard.writeText(`${text}\n${url}`); toast(t('share.copied'));
  } catch (e) { if (e?.name !== 'AbortError') prompt(t('share.copyPrompt'), url); }
}

/* ---------------- story cards (1080×1920) ---------------- */
const W = 1080, H = 1920;

export function myCard() {
  const days = Object.values(S.history);
  const steps = days.reduce((a, r) => a + daySteps(r), 0), dist = days.reduce((a, r) => a + dayDist(r), 0);
  const visited = Object.entries(S.checkins).sort((a, b) => a[1].ts - b[1].ts).map(([id]) => idx.pandal[id]).filter(Boolean);
  const foods = new Set(days.flatMap((r) => r.foods || []));
  return {
    kicker: t('g.cardKicker'), title: t('g.cardTitle'),
    stats: [[fmt(visited.length), t('g.cardPandals')], [fmt(steps), t('g.cardSteps')], [km(dist), t('g.cardKm')], [fmt(foods.size), t('g.cardFood')]],
    lines: visited.slice(-5).reverse().map((p) => '• ' + nm(p)),
    foot: t('g.cardBadges', { n: earned().size }),
  };
}

export function placeCard(id) {
  const p = idx.pandal[id], z = idx.zone[p.zone], day = idx.day[S.day];
  const live = community.stats.byPlace?.[id];
  return {
    kicker: `${dn(day)} · ${z ? (S.prefs.lang === 'bn' && z.short_bn) || z.short : ''}`, title: nm(p), big: true,
    stats: [['★'.repeat(p.popularity), t('g.cardFame')], ...(live?.today ? [[fmt(live.today), t('g.cardHereToday')]] : [])],
    lines: [p.highlight, '', t('g.cardQuiet', { slot: G.data.meta.slots[p.best_slot]?.label || '' }), `🚇 ${p.nearest_metro.name}`],
    foot: t('g.cardAtPandal'),
  };
}

function wrap(ctx, text, maxW) {
  const words = text.split(/\s+/), out = []; let line = '';
  for (const w of words) { const tryL = line ? line + ' ' + w : w; if (ctx.measureText(tryL).width > maxW && line) { out.push(line); line = w; } else line = tryL; }
  if (line) out.push(line);
  return out;
}

/** Draw a card onto a canvas. Pure drawing, no network (so nothing taints the canvas). */
export function drawCard(c) {
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const x = cv.getContext('2d'), F = '"Noto Sans Bengali","Hind Siliguri",system-ui,sans-serif';
  const g = x.createLinearGradient(0, 0, W, H); g.addColorStop(0, '#9F1239'); g.addColorStop(0.55, '#B91C1C'); g.addColorStop(1, '#7C2D12');
  x.fillStyle = g; x.fillRect(0, 0, W, H);
  // alpana-style rings
  x.strokeStyle = 'rgba(253,230,138,.18)'; x.lineWidth = 6;
  for (let r = 160; r < 900; r += 110) { x.beginPath(); x.arc(W - 40, 260, r, 0, Math.PI * 2); x.stroke(); }
  x.fillStyle = '#FDE68A'; x.font = `600 44px ${F}`; x.fillText('🪔 Pujo Parikrama 2026', 80, 170);
  x.fillStyle = 'rgba(255,255,255,.85)'; x.font = `500 40px ${F}`; x.fillText(c.kicker || '', 80, 300);
  x.fillStyle = '#fff'; x.font = `800 ${c.big ? 104 : 120}px ${F}`;
  let y = 430; for (const l of wrap(x, c.title, W - 160).slice(0, 3)) { x.fillText(l, 80, y); y += c.big ? 118 : 132; }
  y += 40;
  const cols = c.stats.length > 1 ? 2 : 1, cw = (W - 160 - 40) / cols;
  c.stats.forEach(([v, label], i) => {
    const cx = 80 + (i % cols) * (cw + 40), cy = y + Math.floor(i / cols) * 250;
    x.fillStyle = 'rgba(255,255,255,.12)'; x.beginPath(); x.roundRect(cx, cy, cw, 210, 36); x.fill();
    x.fillStyle = '#FDE68A'; x.font = `800 96px ${F}`; x.fillText(v, cx + 40, cy + 115);
    x.fillStyle = 'rgba(255,255,255,.9)'; x.font = `500 38px ${F}`; x.fillText(label, cx + 40, cy + 175);
  });
  y += Math.ceil(c.stats.length / cols) * 250 + 40;
  x.fillStyle = '#fff'; x.font = `500 46px ${F}`;
  for (const l of c.lines.slice(0, 7)) { if (!l) { y += 30; continue; } for (const s of wrap(x, l, W - 160).slice(0, 4)) { x.fillText(s, 80, y); y += 64; } }
  x.fillStyle = 'rgba(255,255,255,.9)'; x.font = `600 44px ${F}`; x.fillText(c.foot || '', 80, H - 300);
  x.fillStyle = '#FDE68A'; x.beginPath(); x.roundRect(80, H - 240, W - 160, 130, 65); x.fill();
  x.fillStyle = '#7F1D1D'; x.font = `800 46px ${F}`; x.textAlign = 'center'; x.fillText(t('g.cardCta'), W / 2, H - 160);
  x.textAlign = 'left'; x.fillStyle = 'rgba(255,255,255,.75)'; x.font = `500 32px ${F}`;
  x.fillText(BASE().replace(/^https?:\/\//, '').replace(/\/$/, ''), 80, H - 50);
  return cv;
}

export async function shareCard(card, text, filename) {
  const cv = drawCard(card);
  const blob = await new Promise((r) => cv.toBlob(r, 'image/png'));
  const file = new File([blob], filename, { type: 'image/png' });
  try {
    if (navigator.canShare?.({ files: [file] })) { await navigator.share({ files: [file], text }); return 'shared'; }
  } catch (e) { if (e?.name === 'AbortError') return 'cancelled'; }
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = filename;
  document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  toast(t('g.cardSaved'));
  return 'downloaded';
}
