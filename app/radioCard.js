/* Pujo Radio on Home: a vintage valve radio whose screen is YouTube's player, five stations of official
 * uploads, and a small pause button that follows you to other tabs while it plays. */
import { t, esc } from './state.js';
import { $, toast } from './ui.js';
import * as radio from './radio.js';

const ORDER = ['mahalaya', 'dhak', 'gaan', 'arati', 'bijoya'];
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
      <div class="radio-screen"><div class="screen-idle" aria-hidden="true">${'<i></i>'.repeat(7)}</div><div id="ytHost"></div></div>
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

/* A pause button on the other tabs while music plays. */
let mini = null;
function syncMini() {
  if (!mini) return;
  const tr = radio.status().track;
  mini.hidden = !radio.playing();
  mini.setAttribute('aria-label', `${t('r.pause')}: ${tr?.title || ''}`);
}
export function initMini() {
  mini = document.createElement('button');
  mini.id = 'radioMini'; mini.type = 'button'; mini.className = 'radio-mini'; mini.hidden = true;
  mini.innerHTML = '<span class="mini-ic" aria-hidden="true">♪</span><span class="mini-p" aria-hidden="true">❚❚</span>';
  document.body.appendChild(mini);
  mini.onclick = () => { radio.pause(); };
  radio.onChange(syncMini);
}
