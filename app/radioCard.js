/* Pujo Radio on Home: a "now playing" stage, tap pads (a dhak stroke, the shankh), swipeable station tiles and
 * a fold-away song list. YouTube tracks show YouTube's player in the gold-framed 200 x 200 window (its terms need
 * it visible at that size); the hosted dhak recording just shows the station art.
 *
 * Dhak on arrival: browsers don't allow sound before the visitor touches the page, so the hosted dhak recording
 * (no ads, no channel intro) is cued at load and starts on the first tap anywhere. Pausing is remembered, so
 * people who don't want it aren't greeted by it again. Skipped in low-data mode.
 * The sticky cluster works from any tab: 🥁 plays a dhak stroke, 🐚 the shankh, the badge plays/pauses music. */
import { S, t, esc, store } from './state.js';
import { $, toast, go } from './ui.js';
import * as radio from './radio.js';
import * as sfx from './sfx.js';

const ORDER = ['mahalaya', 'dhak', 'gaan', 'arati', 'bijoya'];
const ART = {
  mahalaya: { bn: 'মহালয়া', em: '🌄', bg: 'linear-gradient(160deg,#F59E0B,#B45309 55%,#7C2D12)' },
  dhak: { bn: 'ঢাকের বাদ্যি', em: '🥁', bg: 'linear-gradient(160deg,#DC2626,#9F1239 55%,#4C0519)' },
  gaan: { bn: 'পুজোর গান', em: '🎶', bg: 'linear-gradient(160deg,#DB2777,#9D174D 55%,#500724)' },
  arati: { bn: 'আরতি', em: '🪔', bg: 'linear-gradient(160deg,#EAB308,#C2410C 55%,#7C2D12)' },
  bijoya: { bn: 'বিজয়া', em: '🌊', bg: 'linear-gradient(160deg,#0EA5E9,#1E3A8A 60%,#172554)' },
};
const AUTO = { station: 'dhak', track: 0 }; // the hosted dhak recording
const YTM = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="#FF0033"/><circle cx="12" cy="12" r="5.6" fill="none" stroke="#fff" stroke-width="1.4"/><path d="M10.3 9.4v5.2l4.4-2.6z" fill="#fff"/></svg>';
let card = null;

/** Built once; later calls only refresh text and lists, never the player window. */
export function radioCard() {
  if (card) { refresh(); return card; }
  card = document.createElement('section');
  card.className = 'radio-card';
  card.setAttribute('aria-labelledby', 'radioTitle');
  card.innerHTML = `<div class="radio-head"></div>
    <div class="np">
      <div class="np-art"><div class="np-idle" aria-hidden="true"></div><div id="ytHost"></div><i class="halo" aria-hidden="true"></i></div>
      <div class="np-info"></div>
      <div class="np-ctrl"></div>
      <div class="pads">
        <button type="button" class="pad" data-sfx="dhak"><span aria-hidden="true">🥁</span><b></b></button>
        <button type="button" class="pad" data-sfx="shankh"><span aria-hidden="true">🐚</span><b></b></button>
      </div>
    </div>
    <div class="st-tiles" role="radiogroup"></div>
    <details class="tracks-wrap"><summary></summary><ol class="tracks"></ol></details>
    <div class="radio-foot-note"></div>`;
  radio.attach($('#ytHost', card));
  radio.onChange(refresh);
  radio.loadMusic().then(refresh);
  card.onclick = onClick;
  refresh();
  return card;
}

function refresh() {
  if (!card) return;
  const st = radio.status(), on = radio.playing(), cur = st.station || 'dhak', tr = st.track, art = ART[cur];
  const list = radio.stations().find((s) => s.id === cur)?.tracks || [];
  card.classList.toggle('live', st.state !== 'idle');
  card.classList.toggle('yt', !!tr?.yt);
  card.querySelector('[data-sfx="dhak"] b').textContent = t('r.padDhak');
  card.querySelector('[data-sfx="shankh"] b').textContent = t('r.padShankh');
  card.classList.toggle('playing', on);
  card.style.setProperty('--st-bg', art.bg);
  $('.radio-head', card).innerHTML = `<div class="r-eyebrow" lang="bn">পুজো রেডিও</div><h2 id="radioTitle">${t('r.title')}</h2><p>${t('r.sub')}</p>`;
  $('.np-idle', card).innerHTML = `<span class="em">${art.em}</span><span class="bn" lang="bn">${art.bn}</span>`;
  $('.np-info', card).innerHTML = `<div class="np-station"><span lang="bn">${art.bn}</span> · ${t('r.' + cur)}</div>
    <div class="np-title">${tr ? esc(tr.title) : t('r.idle')}</div>
    <div class="np-artist">${tr ? `${esc(tr.artist)} · <span class="lbl">${esc(tr.label)}</span>` : t('r.idleSub')}</div>`;
  $('.np-ctrl', card).innerHTML = `
    <button type="button" class="np-btn" id="radioPrev" aria-label="${t('r.prev')}">⏮</button>
    <button type="button" class="np-btn play" id="radioPlay" aria-pressed="${on}" aria-label="${on ? t('r.pause') : t('r.play')}">${on ? '❚❚' : '▶'}</button>
    <button type="button" class="np-btn" id="radioNext" aria-label="${t('r.next')}">⏭</button>
    ${tr?.yt ? `<a class="np-btn ytm" href="https://music.youtube.com/watch?v=${tr.yt}" target="_blank" rel="noopener" aria-label="${t('r.inYtm')}">${YTM}</a>` : ''}`;
  $('.st-tiles', card).setAttribute('aria-label', t('r.stations'));
  $('.st-tiles', card).innerHTML = ORDER.map((k) => `<button type="button" role="radio" class="st-tile" data-station="${k}" aria-checked="${st.station === k && st.state !== 'idle'}" style="--tile:${ART[k].bg}">
      <span class="em" aria-hidden="true">${ART[k].em}</span><span class="bn" lang="bn">${ART[k].bn}</span><span class="en">${t('r.' + k)}</span>
      ${st.station === k && on ? '<span class="eqb" aria-hidden="true"><i></i><i></i><i></i></span>' : ''}</button>`).join('');
  $('.tracks-wrap summary', card).innerHTML = `${t('r.songs', { station: t('r.' + cur), n: list.length })}`;
  $('.tracks', card).innerHTML = list.map((x, i) => `<li><button type="button" data-track="${i}" aria-current="${st.station === cur && st.idx === i && st.state !== 'idle'}">
      <span class="tn">${esc(x.title)}</span><span class="ta">${esc(x.artist)} · ${esc(x.dur)}</span></button></li>`).join('');
  $('.radio-foot-note', card).innerHTML = `<p class="radio-credit">${t('r.credit')} ${t('r.soundCredit')}</p>
    <div class="radio-links"><span>${t('r.more')}</span>
      <a href="https://music.youtube.com/search?q=durga+puja+songs" target="_blank" rel="noopener">YouTube Music</a>
      <a href="https://open.spotify.com/search/durga%20puja" target="_blank" rel="noopener">Spotify</a></div>`;
  syncFab();
}

const wantAuto = (v) => store.set('radioAuto', v);
function guard(fn) {
  if (!navigator.onLine && !radio.isAudio()) return toast(t('r.offline'));
  Promise.resolve(fn()).then((ok) => { if (ok === false) toast(t('r.failed')); });
}
function thump(el) { el.classList.remove('hit'); void el.offsetWidth; el.classList.add('hit'); }
function onClick(e) {
  const fx = e.target.closest('[data-sfx]');
  if (fx) { sfx.play(fx.dataset.sfx); navigator.vibrate?.(fx.dataset.sfx === 'dhak' ? 15 : 30); return thump(fx); }
  if (e.target.closest('.np-art') && !radio.status().track?.yt) { sfx.play('dhak'); return thump($('.np-art', card)); }
  const st = e.target.closest('[data-station]')?.dataset.station;
  if (st) { wantAuto(true); return guard(() => radio.play(st, 0)); }
  const tr = e.target.closest('[data-track]')?.dataset.track;
  if (tr != null) { wantAuto(true); return guard(() => radio.play(radio.status().station || 'dhak', +tr)); }
  if (e.target.closest('#radioPlay')) { const on = radio.playing(); wantAuto(!on); return guard(() => (on ? radio.pause() : radio.toggle())); }
  if (e.target.closest('#radioNext')) return guard(() => radio.next());
  if (e.target.closest('#radioPrev')) return guard(() => radio.prev());
}

/* Sticky cluster: 🥁 a dhak stroke, 🐚 the shankh, badge = play/pause music. Hidden while the radio card is on screen. */
let fab = null, cardVisible = false;
function syncFab() {
  if (!fab) return;
  const tr = radio.status().track, on = radio.playing();
  fab.classList.toggle('on', on);
  fab.hidden = cardVisible;
  const pb = $('#radioFabPlay', fab);
  pb.setAttribute('aria-pressed', String(on));
  pb.setAttribute('aria-label', on ? `${t('r.pause')}: ${tr?.title || ''}` : `${t('r.play')}: ${t('r.title')}`);
  pb.textContent = on ? '❚❚' : '▶';
  $('#radioFab', fab).setAttribute('aria-label', t('r.padDhak'));
  $('#radioFabShankh', fab).setAttribute('aria-label', t('r.padShankh'));
}
export function initMini() {
  fab = document.createElement('div');
  fab.className = 'radio-fab-wrap';
  fab.innerHTML = `<button type="button" class="fab-mini" id="radioFabShankh">🐚</button>
    <button type="button" class="radio-fab" id="radioFab"><span class="fab-ic" aria-hidden="true">🥁</span><span class="fab-ring" aria-hidden="true"></span></button>
    <button type="button" class="fab-state" id="radioFabPlay">▶</button>`;
  document.body.appendChild(fab);
  fab.onclick = (e) => {
    e.stopPropagation();
    if (e.target.closest('#radioFabShankh')) { sfx.play('shankh'); return thump($('#radioFabShankh', fab)); }
    if (e.target.closest('#radioFab')) { sfx.play('dhak'); navigator.vibrate?.(15); return thump($('#radioFab', fab)); }
    if (!e.target.closest('#radioFabPlay')) return;
    if (radio.playing()) { wantAuto(false); radio.pause(); return; }
    wantAuto(true);
    if (radio.status().state !== 'idle') return guard(() => radio.playNow());
    guard(() => radio.play(AUTO.station, AUTO.track));
  };
  radio.onChange(syncFab);
  addEventListener('viewchange', viewChanged);
  syncFab();
  armAutoplay();
}

/* Dhak on arrival: cue now, play on the first tap anywhere (unless they paused it before). */
function armAutoplay() {
  const first = () => { sfx.preload(); removeEventListener('pointerup', first, true); };
  addEventListener('pointerup', first, true);
  if (store.get('radioAuto', true) === false || S.prefs.lowData) return;
  radio.cue(AUTO.station, AUTO.track);
  const start = (e) => {
    if (e.target.closest?.('.radio-card, .radio-fab-wrap')) return disarm(); // they're using the radio themselves
    disarm();
    if (radio.status().state === 'cued') { radio.playNow(); toast(t('r.autoToast'), 4200); }
  };
  const evs = ['pointerup', 'touchend', 'keydown'];
  const disarm = () => evs.forEach((ev) => removeEventListener(ev, start, true));
  evs.forEach((ev) => addEventListener(ev, start, true));
}

let io = null;
export function watchCard() {
  if (!card || !('IntersectionObserver' in window)) return;
  io ||= new IntersectionObserver(([e]) => { cardVisible = e.isIntersecting && document.querySelector('#view-home.active') != null; syncFab(); }, { threshold: 0.35 });
  io.observe(card);
}
export function viewChanged() { if (!document.querySelector('#view-home.active')) { cardVisible = false; syncFab(); } }
