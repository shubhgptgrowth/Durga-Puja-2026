/* Celebrations: marigold and rose petals with a "জয় মা!" card and three dhak beats when a check-in or
 * "I ate here" goes through, and a medallion pop-up (with Share) when a badge unlocks. Listens for the
 * pp:visit and pp:badge events from actions.js. Calmer with reduced motion: no petals, just the card. */
import { S, idx, t, esc, nm } from './state.js';
import * as sfx from './sfx.js';
import { shareBadge } from './badges.js';

const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const PETALS = ['#F59E0B', '#FBBF24', '#EA580C', '#F97316', '#C8102E', '#FDE68A'];
let busyUntil = 0;
const queue = [];

function petals(ms = 2600) {
  if (reduced()) return;
  const cv = document.createElement('canvas'), dpr = Math.min(2, devicePixelRatio || 1);
  cv.className = 'petal-canvas';
  cv.width = innerWidth * dpr; cv.height = innerHeight * dpr;
  document.body.appendChild(cv);
  const x = cv.getContext('2d'); x.scale(dpr, dpr);
  const cx = innerWidth / 2, cy = innerHeight * 0.42;
  const ps = Array.from({ length: 90 }, () => {
    const a = Math.random() * Math.PI * 2, v = 3 + Math.random() * 7;
    return { x: cx, y: cy, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 4, r: 4 + Math.random() * 6, rot: Math.random() * 6, vr: (Math.random() - 0.5) * 0.3,
      c: PETALS[(Math.random() * PETALS.length) | 0], w: 0.45 + Math.random() * 0.4 };
  });
  const t0 = performance.now();
  const step = (now) => {
    const k = (now - t0) / ms;
    x.clearRect(0, 0, innerWidth, innerHeight);
    for (const p of ps) {
      p.vy += 0.18; p.vx *= 0.985; p.vy *= 0.985; p.x += p.vx; p.y += p.vy; p.rot += p.vr;
      x.save(); x.globalAlpha = Math.max(0, 1 - k * k); x.translate(p.x, p.y); x.rotate(p.rot);
      x.fillStyle = p.c; x.beginPath(); x.ellipse(0, 0, p.r, p.r * p.w, 0, 0, Math.PI * 2); x.fill(); x.restore();
    }
    if (k < 1) requestAnimationFrame(step); else cv.remove();
  };
  requestAnimationFrame(step);
}

function beats() { [0, 170, 340].forEach((d) => setTimeout(() => sfx.play('dhak'), d)); navigator.vibrate?.([30, 60, 30, 60, 60]); }

function cheer(id, kind) {
  const p = idx.pandal[id] || idx.food[id];
  const el = document.createElement('div');
  el.className = 'cheer'; el.setAttribute('role', 'status');
  el.innerHTML = `<div class="cheer-card"><div class="cheer-bn" lang="bn">${kind === 'food' ? 'আহা! পেট-পুজো' : 'জয় মা!'}</div>
    <b>${esc(t(kind === 'food' ? 'cel.ate' : 'cel.here', { name: p ? nm(p) : '' }))}</b></div>`;
  document.body.appendChild(el);
  el.onclick = () => el.remove();
  setTimeout(() => el.classList.add('out'), 2100);
  setTimeout(() => el.remove(), 2500);
  petals(); beats();
  busyUntil = Date.now() + 2400;
}

/** The badge pop-up: a medallion that springs in, with Share and Done. Its own overlay, so the page underneath stays. */
function showBadge(b) {
  if (Date.now() < busyUntil) { queue.push(b); return setTimeout(next, busyUntil - Date.now() + 150); }
  petals(2200);
  sfx.play('shankh');
  const el = document.createElement('div');
  el.className = 'badge-modal'; el.setAttribute('role', 'dialog'); el.setAttribute('aria-modal', 'true'); el.setAttribute('aria-label', t('bd.unlocked'));
  el.innerHTML = `<div class="badge-pop card-pop">
      <div class="medal" aria-hidden="true"><span>${b.em}</span><i class="rays"></i></div>
      <p class="badge-eyebrow">${t('bd.unlocked')}</p>
      <h2>${esc(S.prefs.lang === 'bn' ? b.bn : b.name)}</h2>
      <p class="fine">${t('b.' + b.id)}</p>
      <div class="btn-row" style="justify-content:center;margin-top:14px">
        <button class="btn primary" id="bdShare">📸 ${t('bd.share')}</button><button class="btn" id="bdDone">${t('bd.done')}</button></div></div>`;
  document.body.appendChild(el);
  const close = () => { el.remove(); busyUntil = 0; next(); };
  el.querySelector('#bdDone').onclick = close;
  el.onclick = (e) => { if (e.target === el) close(); };
  let touched = false;
  el.querySelector('#bdShare').onclick = () => { touched = true; shareBadge(b); };
  el.querySelector('#bdDone').focus();
  setTimeout(() => { if (!touched && el.isConnected) close(); }, 7000); // celebrate, then get out of the way
  busyUntil = Date.now() + 60e3; // the next badge waits until this one is closed
}
function next() { if (document.querySelector('.badge-modal')) return; const b = queue.shift(); if (b) showBadge(b); }

export function initCelebrations() {
  document.addEventListener('pp:visit', (e) => cheer(e.detail.id, e.detail.kind));
  // A badge is decided as the visit is recorded, just before its petals: show it once they've fallen.
  document.addEventListener('pp:badge', (e) => setTimeout(() => showBadge(e.detail), 2700));
}
