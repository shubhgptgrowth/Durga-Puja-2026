/* Pujo Radio on Home: a vintage valve radio. Its small square window is YouTube's player (YouTube Music has
 * no embeddable player; YouTube's terms need the player visible, at least 200 x 200), flanked by speaker grilles.
 * A sticky radio button floats over the app from the start; tapping it, or scrolling to the card, opens the radio. */
import { t, esc } from './state.js';
import { $, toast, go } from './ui.js';
import * as radio from './radio.js';

const ORDER = ['mahalaya', 'dhak', 'gaan', 'arati', 'bijoya'];
const YTM = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="#FF0033"/><circle cx="12" cy="12" r="5.6" fill="none" stroke="#fff" stroke-width="1.4"/><path d="M10.3 9.4v5.2l4.4-2.6z" fill="#fff"/></svg>';
let card = null;

/** Built once; later calls only refresh the controls and lists, never the player. */
export function radioCard() {
  if (card) { refresh(); return card; }
  card = document.createElement('section');
  card.className = 'radio-card';
  card.setAttribute('aria-labelledby', 'radioTitle');
  card.innerHTML = `<div class="radio-head"></div>
    <div class="radio">
      <div class="radio-brand" aria-hidden="true">পুজো রেডিও</div>
      <div class="radio-face"><div class="grille" aria-hidden="true"></div>
        <div class="radio-screen"><div class="screen-idle" aria-hidden="true"><span class="om">ॐ</span><span class="tune"></span></div><div id="ytHost"></div></div>
        <div class="grille" aria-hidden="true"></div></div>
      <div class="radio-ui"></div>
    </div>
    <div class="radio-lists"></div>`;
  radio.attach($('#ytHost', card));
  radio.onChange(refresh);
  radio.loadMusic().then(refresh);
  card.onclick = onClick;
  refresh();
  return card;
}

function refresh() {
  if (!card) return;
  const st = radio.status(), on = radio.playing(), cur = st.station || 'mahalaya', pos = ORDER.indexOf(cur), tr = st.track;
  const list = radio.stations().find((s) => s.id === cur)?.tracks || [];
  card.classList.toggle('live', st.state !== 'idle');
  $('.radio-head', card).innerHTML = `<h2 id="radioTitle">${t('r.title')}</h2><p>${t('r.sub')}</p>`;
  $('.radio-ui', card).innerHTML = `
    <div class="dial" aria-hidden="true"><div class="ticks"></div>${ORDER.map((k) => `<span>${t('r.' + k + 'Dial')}</span>`).join('')}<b class="needle" style="left:${10 + pos * 20}%"></b></div>
    <div class="radio-foot">
      <button type="button" class="knob" id="radioPrev" aria-label="${t('r.prev')}">⏮</button>
      <button type="button" class="knob play" id="radioPlay" aria-pressed="${on}" aria-label="${on ? t('r.pause') : t('r.play')}">${on ? '❚❚' : '▶'}</button>
      <button type="button" class="knob" id="radioNext" aria-label="${t('r.next')}">⏭</button>
      <span class="radio-now">${tr ? `<b>${esc(tr.title)}</b><small>${esc(tr.artist)}</small>` : t('r.idle')}</span>
      ${tr ? `<a class="knob ytm" href="https://music.youtube.com/watch?v=${tr.yt}" target="_blank" rel="noopener" aria-label="${t('r.inYtm')}">${YTM}</a>` : ''}
    </div>`;
  $('.radio-lists', card).innerHTML = `
    <div class="stations" role="radiogroup" aria-label="${t('r.stations')}">${ORDER.map((k) => `<button type="button" role="radio" data-station="${k}" aria-checked="${st.station === k}">
      <b>${t('r.' + k)}</b><small>${t('r.' + k + 'Sub')}</small></button>`).join('')}</div>
    ${list.length ? `<ol class="tracks">${list.map((x, i) => `<li><button type="button" data-track="${i}" aria-current="${st.station === cur && st.idx === i && st.state !== 'idle'}">
      <span class="tn">${esc(x.title)}</span><span class="ta">${esc(x.artist)} · ${esc(x.dur)}</span></button></li>`).join('')}</ol>` : ''}
    <p class="radio-credit">${t('r.credit')}</p>
    <div class="radio-links"><span>${t('r.more')}</span>
      <a href="https://music.youtube.com/search?q=durga+puja+songs" target="_blank" rel="noopener">YouTube Music</a>
      <a href="https://open.spotify.com/search/durga%20puja" target="_blank" rel="noopener">Spotify</a></div>`;
  syncMini();
}

function guard(fn) {
  if (!navigator.onLine) return toast(t('r.offline'));
  Promise.resolve(fn()).then((ok) => { if (ok === false) toast(t('r.failed')); });
}
function onClick(e) {
  const st = e.target.closest('[data-station]')?.dataset.station;
  if (st) return guard(() => radio.play(st, 0));
  const tr = e.target.closest('[data-track]')?.dataset.track;
  if (tr != null) return guard(() => radio.play(radio.status().station || 'mahalaya', +tr));
  if (e.target.closest('#radioPlay')) return guard(() => radio.toggle());
  if (e.target.closest('#radioNext')) return guard(() => radio.next());
  if (e.target.closest('#radioPrev')) return guard(() => radio.prev());
}

/* The sticky radio button: there from the start, on every tab, until the radio card itself is on screen. */
let fab = null, cardVisible = false;
function syncMini() {
  if (!fab) return;
  const tr = radio.status().track, on = radio.playing();
  fab.classList.toggle('on', on);
  fab.hidden = cardVisible;
  fab.setAttribute('aria-label', on ? `${t('r.nowPlaying')}: ${tr?.title || ''}` : t('r.open'));
}
export function initMini() {
  fab = document.createElement('button');
  fab.id = 'radioFab'; fab.type = 'button'; fab.className = 'radio-fab';
  fab.innerHTML = `<span class="fab-ic" aria-hidden="true"><svg viewBox="0 0 32 32"><rect x="3" y="9" width="26" height="18" rx="4" fill="#7A3B12"/><rect x="6" y="12" width="11" height="12" rx="2" fill="#E9D8B4"/><circle cx="23" cy="16" r="2.6" fill="#E8B923"/><circle cx="23" cy="22.5" r="1.6" fill="#E8B923"/><path d="M9 9 20 3" stroke="#7A3B12" stroke-width="1.8" stroke-linecap="round"/>
    <g class="eq"><rect x="8" y="17" width="1.8" height="5" fill="#8E0E1C"/><rect x="11" y="15" width="1.8" height="7" fill="#8E0E1C"/><rect x="14" y="18" width="1.8" height="4" fill="#8E0E1C"/></g></svg></span>`;
  document.body.appendChild(fab);
  fab.onclick = () => {
    go('home', { keepScroll: true });
    requestAnimationFrame(() => {
      const c = card; if (!c) return;
      c.scrollIntoView({ behavior: 'smooth', block: 'center' });
      c.classList.remove('arrive'); void c.offsetWidth; c.classList.add('arrive');
    });
  };
  radio.onChange(syncMini);
  addEventListener('viewchange', viewChanged);
  syncMini();
}
/** Called by Home after it renders: hide the sticky button while the card is visible. */
let io = null;
export function watchCard() {
  if (!card || !('IntersectionObserver' in window)) return;
  io ||= new IntersectionObserver(([e]) => { cardVisible = e.isIntersecting && document.querySelector('#view-home.active') != null; card.classList.toggle('open', e.isIntersecting); syncMini(); }, { threshold: 0.35 });
  io.observe(card);
}
export function viewChanged() { if (!document.querySelector('#view-home.active')) { cardVisible = false; syncMini(); } }
