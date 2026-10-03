/* Pujo Radio engine. Two kinds of track (app/data/music.json):
 * - "audio": freely licensed recordings hosted in app/audio (the dhak). Played by an <audio> element: no ads, no
 *   channel intro, starts instantly and works offline.
 * - "yt": the labels' official uploads, played through YouTube's embedded player so every play is licensed.
 * The YouTube iframe lives in the Home card, which is built once and never re-rendered, so music keeps playing
 * while you browse other tabs. */

let data = null, apiReady = null, player = null, host = null, ytReady = false;
let station = null, idx = 0, state = 'idle'; // idle | cued | loading | playing | paused
const audio = new Audio();
audio.preload = 'none';
const listeners = new Set();
const emit = () => listeners.forEach((fn) => fn());

export const onChange = (fn) => { listeners.add(fn); return () => listeners.delete(fn); };
export const status = () => ({ state, station, idx, track: current() });
export const stations = () => data?.stations || [];
export function current() { const s = stations().find((x) => x.id === station); return s ? s.tracks[idx] : null; }
export const isAudio = () => !!current()?.audio;

export function loadMusic() {
  data ||= fetch('data/music.json').then((r) => r.json()).then((d) => (data = d)).catch(() => { data = null; return null; });
  return Promise.resolve(data);
}

function loadApi() {
  apiReady ||= new Promise((resolve, reject) => {
    if (window.YT?.Player) return resolve(window.YT);
    const prev = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => { prev?.(); resolve(window.YT); };
    const s = document.createElement('script');
    s.src = 'https://www.youtube.com/iframe_api';
    s.onerror = () => { apiReady = null; reject(new Error('youtube')); };
    document.head.appendChild(s);
  });
  return apiReady;
}

/** The element the YouTube iframe replaces. Called once by the Home card. */
export function attach(el) { host = el; }

function onYtState(e) {
  if (isAudio()) return; // a stale event from the paused YouTube player
  const YT = window.YT;
  if (e.data === YT.PlayerState.PLAYING) state = 'playing';
  else if (e.data === YT.PlayerState.PAUSED) state = 'paused';
  else if (e.data === YT.PlayerState.BUFFERING) state = 'loading';
  else if (e.data === YT.PlayerState.ENDED) return next();
  emit();
}
audio.addEventListener('playing', () => { if (isAudio()) { state = 'playing'; emit(); } });
audio.addEventListener('pause', () => { if (isAudio() && state !== 'idle') { state = 'paused'; emit(); } });
audio.addEventListener('ended', () => { if (isAudio()) next(); });

function select(stationId, i) {
  const s = stations().find((x) => x.id === stationId);
  if (!s) return null;
  station = stationId; idx = (i + s.tracks.length) % s.tracks.length;
  return s.tracks[idx];
}
function playAudio(tr) {
  if (player && ytReady) player.pauseVideo();
  if (!audio.src.endsWith(tr.audio)) audio.src = tr.audio;
  audio.loop = !!tr.loop;
  state = 'loading'; emit();
  const p = audio.play();
  p?.catch(() => { state = 'paused'; emit(); });
  return true;
}

export async function play(stationId, i = 0) {
  await loadMusic();
  const tr = select(stationId, i);
  if (!tr) return false;
  if (tr.audio) return playAudio(tr);
  audio.pause();
  if (!host) return false;
  state = 'loading'; emit();
  try {
    const YT = await loadApi();
    if (player) player.loadVideoById(tr.yt);
    else {
      player = new YT.Player(host, {
        host: 'https://www.youtube-nocookie.com', videoId: tr.yt, width: '100%', height: '100%',
        playerVars: { autoplay: 1, playsinline: 1, rel: 0, modestbranding: 1, controls: 0, iv_load_policy: 3, fs: 0, disablekb: 1 },
        events: { onReady: (e) => { ytReady = true; e.target.playVideo(); }, onStateChange: onYtState, onError: () => next() },
      });
    }
    return true;
  } catch { state = 'idle'; emit(); return false; }
}

/** Get a track ready so a later tap can start it instantly (browsers only allow sound from inside a tap). */
export async function cue(stationId, i = 0) {
  await loadMusic();
  if (state !== 'idle') return false;
  const tr = select(stationId, i);
  if (!tr?.audio) return false; // only the hosted dhak is cued; YouTube tracks load when chosen
  audio.src = tr.audio; audio.loop = !!tr.loop; audio.preload = 'auto';
  state = 'cued'; emit();
  return true;
}
/** Start whatever is loaded. Call from inside a tap. */
export function playNow() {
  const tr = current();
  if (tr?.audio) return playAudio(tr);
  if (player && ytReady) { state = 'loading'; player.playVideo(); emit(); return true; }
  return play(station || 'dhak', idx);
}
export function toggle() {
  if (state === 'idle') return play(station || 'dhak', idx);
  if (state === 'cued') return playNow();
  if (state === 'playing' || state === 'loading') return pause();
  return playNow();
}
export const next = () => play(station || 'dhak', idx + 1);
export const prev = () => play(station || 'dhak', idx - 1);
export function pause() {
  if (isAudio()) audio.pause();
  else if (player && ytReady) player.pauseVideo();
}
export const playing = () => state === 'playing' || state === 'loading';
