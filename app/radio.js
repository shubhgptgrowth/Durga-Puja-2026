/* Pujo Radio engine: plays official uploads (app/data/music.json) through YouTube's embedded player,
 * so every play is licensed and counted for the label. The player iframe lives in the Home card,
 * which is built once and never re-rendered, so music keeps playing while you browse other tabs. */

let data = null, apiReady = null, player = null, host = null;
let station = null, idx = 0, state = 'idle'; // idle | loading | playing | paused
const listeners = new Set();
const emit = () => listeners.forEach((fn) => fn());

export const onChange = (fn) => { listeners.add(fn); return () => listeners.delete(fn); };
export const status = () => ({ state, station, idx, track: current() });
export const stations = () => data?.stations || [];
export function current() { const s = stations().find((x) => x.id === station); return s ? s.tracks[idx] : null; }

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

/** The element the player iframe replaces. Called once by the Home card. */
export function attach(el) { host = el; }

function onState(e) {
  const YT = window.YT;
  if (e.data === YT.PlayerState.PLAYING) state = 'playing';
  else if (e.data === YT.PlayerState.PAUSED) state = 'paused';
  else if (e.data === YT.PlayerState.BUFFERING) state = 'loading';
  else if (e.data === YT.PlayerState.ENDED) return next();
  emit();
}

export async function play(stationId, i = 0) {
  await loadMusic();
  const s = stations().find((x) => x.id === stationId);
  if (!s || !host) return false;
  station = stationId; idx = (i + s.tracks.length) % s.tracks.length; state = 'loading'; emit();
  const id = s.tracks[idx].yt;
  try {
    const YT = await loadApi();
    if (player) player.loadVideoById(id);
    else {
      player = new YT.Player(host, {
        host: 'https://www.youtube-nocookie.com', videoId: id, width: '100%', height: '100%',
        playerVars: { autoplay: 1, playsinline: 1, rel: 0, modestbranding: 1 },
        events: { onReady: (e) => e.target.playVideo(), onStateChange: onState, onError: () => next() },
      });
    }
    return true;
  } catch { state = 'idle'; emit(); return false; }
}
export function toggle() {
  if (!player || state === 'idle') return play(station || 'mahalaya', idx);
  state === 'playing' ? player.pauseVideo() : player.playVideo();
}
export const next = () => play(station || 'mahalaya', idx + 1);
export const prev = () => play(station || 'mahalaya', idx - 1);
export const pause = () => { if (player && state === 'playing') player.pauseVideo(); };
export const playing = () => state === 'playing' || state === 'loading';
