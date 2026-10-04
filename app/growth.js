/* Growth: which link brought someone (?src=), an anonymous once-per-boot open count, deep links to
 * places (#p=<id>), WhatsApp/share buttons, and shareable 1080×1920 story cards for Instagram and
 * WhatsApp Status. See docs/marketing/PLAN.md for the link codes. */
import { S, G, idx, t, store, community, nm, fmt, km, dn, todayKey } from './state.js';
import { toast } from './ui.js';
import { daySteps, dayDist, earned } from './actions.js';
import { track } from './analytics.js';

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

export function deviceId() {
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

const WA_ICON = '<svg class="wa-ico" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2Zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8s-.4-.1-.6.1-.7.8-.8 1-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.3-.4.2-.4.7-1.3a.5.5 0 0 0 0-.4l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.7 11.8 11.8 0 0 0 4.5 4c1.7.7 2.3.8 3.2.7a2.7 2.7 0 0 0 1.8-1.3 2.2 2.2 0 0 0 .2-1.3c-.1-.1-.3-.2-.5-.3Z"/></svg>';

/** One share button. Opens WhatsApp with the place's link; on a pandal, a phone that can share images gets the
 * story card too (WhatsApp, Instagram, anything), so one button covers WhatsApp, Story card and Share. */
export function shareCtaHtml(id) {
  return `<a class="btn wa" id="waShare" target="_blank" rel="noopener" href="${waUrl(`${placeText(id)}\n${placeLink(id, 'wa_place')}`)}" aria-label="${t('g.shareWa')}">${WA_ICON}<span>${t('g.link')}</span></a>`;
}

export function wireShareCta(el, id) {
  const b = el.querySelector('#waShare');
  if (!b) return;
  b.onclick = (e) => {
    track('share', { place: id, d: 'wa' });
    if (!idx.pandal[id]) return; // eateries: straight to WhatsApp
    let canFiles = false;
    try { canFiles = !!navigator.canShare?.({ files: [new File([''], 'x.png', { type: 'image/png' })] }); } catch { /* old browsers */ }
    if (!canFiles) return; // desktop and older phones: the WhatsApp link
    e.preventDefault();
    shareCard(placeCard(id), `${myName() ? t('g.fromName', { name: myName() }) + ' ' : ''}${placeText(id)}\n${placeLink(id, 'share')}`, `pujo-${id}.png`);
  };
}

export async function shareLink(text, url) {
  track('share', { d: 'link' });
  try {
    if (navigator.share) { await navigator.share({ title: 'Pujo Parikrama', text, url }); return; }
    await navigator.clipboard.writeText(`${text}\n${url}`); toast(t('share.copied'));
  } catch (e) { if (e?.name !== 'AbortError') prompt(t('share.copyPrompt'), url); }
}

/** The name people gave in My Pujo (first name only on cards, so a full name isn't posted publicly). */
export const myName = () => (S.prefs.name || '').trim().split(/\s+/)[0] || '';

/* ---------------- story cards (1080×1920) ---------------- */
const W = 1080, H = 1920;

export function myCard() {
  const days = Object.values(S.history);
  const steps = days.reduce((a, r) => a + daySteps(r), 0), dist = days.reduce((a, r) => a + dayDist(r), 0);
  const visited = Object.entries(S.checkins).sort((a, b) => a[1].ts - b[1].ts).map(([id]) => idx.pandal[id]).filter(Boolean);
  const foods = new Set(days.flatMap((r) => r.foods || []));
  return {
    kicker: t('g.cardKicker'), title: myName() ? t('g.cardTitleName', { name: myName() }) : t('g.cardTitle'),
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
    foot: myName() ? t('g.cardAtPandalName', { name: myName() }) : t('g.cardAtPandal'),
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
  track('share', { d: 'card:' + filename.replace(/\.png$/, '') });
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
