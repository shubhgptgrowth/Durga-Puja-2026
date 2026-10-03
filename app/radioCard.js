/* The Home screen's playful bits: a marigold garland, and "Pujo Radio" (a vintage valve radio and a dhak you can tap). */
import { t } from './state.js';
import { $ } from './ui.js';
import * as radio from './radio.js';

const ORDER = ['agomoni', 'arati', 'dhunuchi', 'bijoya'];
const calm = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

/** A gaanda-phool garland in three swags with mango leaves, drawn once as SVG. */
export function garlandSvg() {
  const W = 360, swags = 3, per = 9, w = W / swags;
  let flowers = '', leaves = '';
  for (let s = 0; s < swags; s++) {
    for (let i = 0; i <= per; i++) {
      const u = i / per, x = s * w + u * w, y = 5 + 16 * Math.sin(Math.PI * u);
      const c = (i + s) % 3 === 0 ? '#FACC15' : '#F97316';
      flowers += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="5.2" fill="${c}"/><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="2" fill="#C2410C" opacity=".55"/>`;
    }
    const lx = s * w;
    leaves += `<path d="M${lx} 6 q-4 10 0 16 q4 -6 0 -16z" fill="#15803D"/><path d="M${lx + 5} 6 q2 9 6 13 q0 -8 -6 -13z" fill="#16A34A"/>`;
  }
  return `<svg class="garland" viewBox="0 0 ${W} 30" preserveAspectRatio="none" aria-hidden="true">${leaves}${flowers}<path d="M${W} 6 q-4 10 0 16 q4 -6 0 -16z" fill="#15803D"/></svg>`;
}

/** A dhak: the barrel drum with its white kash-phool plume. */
const DHAK = `<svg viewBox="0 0 150 160" aria-hidden="true">
  <g class="plume">${[-62, -42, -24, -8, 8, 24, 42, 60].map((a, i) => `<path transform="rotate(${a} 76 70)" d="M76 70 C 74 52, 70 36, 76 ${14 + (i % 2) * 6}" stroke="#FFFDF7" stroke-width="${i % 2 ? 6 : 8}" stroke-linecap="round" fill="none"/>
    <path transform="rotate(${a} 76 70)" d="M76 ${30 + (i % 2) * 4} C 73 26, 74 ${20 + (i % 2) * 6}, 76 ${16 + (i % 2) * 6}" stroke="#E7E1D4" stroke-width="3" stroke-linecap="round" fill="none"/>`).join('')}
    <rect x="73" y="62" width="6" height="16" rx="2" fill="#7C2D12"/></g>
  <g class="drum" transform="rotate(-10 76 112)">
    <rect x="18" y="78" width="116" height="66" rx="30" fill="#9F1239"/>
    <rect x="18" y="78" width="116" height="66" rx="30" fill="url(#dhakShade)"/>
    <polyline points="${Array.from({ length: 12 }, (_, i) => `${30 + i * 8.5},${i % 2 ? 140 : 82}`).join(' ')}" fill="none" stroke="#FEF3C7" stroke-width="2.2"/>
    <rect x="18" y="106" width="116" height="10" fill="#B7791F" opacity=".9"/>
    <ellipse cx="20" cy="111" rx="12" ry="33" fill="#F5E6C8" stroke="#7C2D12" stroke-width="3"/>
    <ellipse cx="132" cy="111" rx="12" ry="33" fill="#F5E6C8" stroke="#7C2D12" stroke-width="3"/>
  </g>
  <line class="stick" x1="122" y1="76" x2="146" y2="40" stroke="#7C2D12" stroke-width="3.5" stroke-linecap="round"/>
  <defs><linearGradient id="dhakShade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".22"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".25"/></linearGradient></defs>
</svg>`;

export function radioHtml() {
  const on = radio.playing(), cur = radio.current() || 'agomoni', pos = ORDER.indexOf(cur);
  return `<section class="radio-card" aria-labelledby="radioTitle">
    <div class="radio-head"><h2 id="radioTitle">${t('r.title')}</h2><p>${t('r.sub')}</p></div>
    <div class="radio-stage">
      <div class="radio ${on ? 'on' : ''}">
        <div class="radio-brand">${t('r.brand')}</div>
        <div class="grille" aria-hidden="true">${'<i></i>'.repeat(9)}</div>
        <div class="dial" aria-hidden="true"><div class="ticks"></div>${ORDER.map((k) => `<span>${t('r.' + k + 'Dial')}</span>`).join('')}<b class="needle" style="left:${12 + pos * 25}%"></b></div>
        <div class="radio-foot">
          <button type="button" class="knob play" id="radioPlay" aria-pressed="${on}" aria-label="${on ? t('r.pause') : t('r.play')}">${on ? '❚❚' : '▶'}</button>
          <span class="radio-now">${on ? t('r.' + cur) : t('r.off')}</span>
          <button type="button" class="knob" id="radioShankh" aria-label="${t('r.shankh')}">🐚</button>
        </div>
      </div>
      <button type="button" class="dhak" id="radioDhak" aria-label="${t('r.tap')}">${DHAK}<span class="dhak-hint">${t('r.tapHint')}</span></button>
    </div>
    <div class="stations" role="radiogroup" aria-label="${t('r.stations')}">${ORDER.map((k) => `<button type="button" role="radio" data-station="${k}" aria-checked="${on && cur === k}">
      <b>${t('r.' + k)}</b><small>${t('r.' + k + 'Sub')}</small></button>`).join('')}</div>
    <div class="radio-links"><span>${t('r.more')}</span>
      <a href="https://www.youtube.com/results?search_query=durga+puja+bengali+songs" target="_blank" rel="noopener">YouTube</a>
      <a href="https://open.spotify.com/search/durga%20puja%20bengali" target="_blank" rel="noopener">Spotify</a></div>
  </section>`;
}

let unbind = null;
export function wireRadio(el) {
  const card = $('.radio-card', el); if (!card) return;
  const rerender = () => { card.outerHTML = radioHtml(); wireRadio(el); };
  const dhak = $('#radioDhak', card), bars = [...card.querySelectorAll('.grille i')];
  const bump = (cls, ms) => { if (calm()) return; dhak.classList.remove(cls); void dhak.offsetWidth; dhak.classList.add(cls); setTimeout(() => dhak.classList.remove(cls), ms); };
  unbind?.();
  unbind = radio.onBeat((kind) => {
    if (kind === 'state') return;
    if (!document.body.contains(card)) return;
    bump(kind === 'boom' ? 'boom' : 'tak', kind === 'boom' ? 220 : 120);
    if (!calm()) bars.forEach((b) => (b.style.transform = `scaleY(${(0.2 + Math.random() * (kind === 'boom' ? 0.8 : 0.5)).toFixed(2)})`));
  });
  card.onclick = (e) => {
    const st = e.target.closest('[data-station]')?.dataset.station;
    if (st) { if (radio.playing() && radio.current() === st) radio.stop(); else radio.play(st); return rerender(); }
    if (e.target.closest('#radioPlay')) { radio.playing() ? radio.stop() : radio.play(radio.current() || 'agomoni'); return rerender(); }
    if (e.target.closest('#radioShankh')) return radio.blowShankh();
    const d = e.target.closest('#radioDhak');
    if (d) {
      const r = d.getBoundingClientRect(), side = e.clientX - r.left < r.width / 2 ? 'boom' : 'tak';
      radio.strike(side); navigator.vibrate?.(side === 'boom' ? 18 : 8);
    }
  };
}

/** A small floating dhak button on the other tabs while the radio plays: tap to stop. */
export function initMini() {
  const b = document.createElement('button');
  b.id = 'radioMini'; b.type = 'button'; b.className = 'radio-mini'; b.hidden = true;
  b.innerHTML = '<span class="mini-ic" aria-hidden="true">🥁</span>';
  document.body.appendChild(b);
  const sync = () => { b.hidden = !radio.playing(); b.setAttribute('aria-label', t('r.stopMini')); };
  radio.onBeat((kind) => {
    if (kind === 'state') return sync();
    if (!calm() && kind === 'boom') { b.classList.remove('beat'); void b.offsetWidth; b.classList.add('beat'); }
  });
  b.onclick = () => { radio.stop(); sync(); };
  sync();
}
