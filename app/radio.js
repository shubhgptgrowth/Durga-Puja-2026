/* Pujo Radio: dhak, kansor, ghanta and shankh, synthesised live with Web Audio.
 * Nothing is downloaded and nothing is recorded music, so it works offline and has no rights issues.
 * Four "stations" are rhythm patterns at different tempos. Listeners get a callback on every drum hit,
 * which the Home screen uses to make the dhak jump and the dial glow. */

let ctx = null, master = null, noise = null, timer = null;
let station = null, step = 0, bar = 0, nextTime = 0;
const listeners = new Set();

/* Patterns are 16 steps per bar. B = bass skin (dhyang), T = stick on the treble skin (tak), K = kansor (bronze plate),
 * G = ghanta (hand bell). Upper case is an accent. F is a fill bar played every 4th bar. */
export const STATIONS = {
  agomoni: { bpm: 100, B: 'X..x..x...X..x..', T: '..x..x.xx..x.x.x', K: 'x...x...x...x...', G: '', F: 'X.x.x.xxX.x.xxxx', shankh: 0 },
  arati: { bpm: 124, B: 'X..x.xX..x..X.x.', T: '.x.xx.x.xx.xx.xx', K: 'x.x.x.x.x.x.x.x.', G: 'x...x...x...x...', F: 'XxxxXxxxXxxxXxXx', shankh: 8 },
  dhunuchi: { bpm: 150, B: 'X.xX.x.xX.xX.xXx', T: 'xx.xxx.xxx.xxx.x', K: 'x.x.x.x.x.x.x.x.', G: '', F: 'XxXxXxXxXXXXxxxx', shankh: 0 },
  bijoya: { bpm: 80, B: 'X.......x..x....', T: '....x.......x.x.', K: 'x.......x.......', G: '', F: 'X...x.x.X..xx.x.', shankh: 4 },
};

function audio() {
  if (ctx) { if (ctx.state === 'suspended') ctx.resume(); return ctx; }
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return null;
  ctx = new AC();
  const comp = ctx.createDynamicsCompressor();
  comp.threshold.value = -14; comp.ratio.value = 4;
  master = ctx.createGain(); master.gain.value = 0.85;
  master.connect(comp); comp.connect(ctx.destination);
  noise = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
  const d = noise.getChannelData(0);
  for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  return ctx;
}

const env = (g, t, peak, decay) => { g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(peak, t + 0.004); g.gain.exponentialRampToValueAtTime(0.0001, t + decay); };
function burst(t, { type = 'bandpass', freq, q = 1, peak, decay }) {
  const src = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain();
  src.buffer = noise; f.type = type; f.frequency.value = freq; f.Q.value = q;
  env(g, t, peak, decay);
  src.connect(f); f.connect(g); g.connect(master);
  src.start(t, Math.random() * 0.5); src.stop(t + decay + 0.05);
}
function tone(t, { type = 'sine', from, to = from, glide = 0.2, peak, decay, dest = master }) {
  const o = ctx.createOscillator(), g = ctx.createGain();
  o.type = type; o.frequency.setValueAtTime(from, t); o.frequency.exponentialRampToValueAtTime(to, t + glide);
  env(g, t, peak, decay);
  o.connect(g); g.connect(dest); o.start(t); o.stop(t + decay + 0.05);
}

/** The big goatskin side: a deep pitch-dropping boom with a leathery thud. */
function dhyang(t, v = 1) {
  tone(t, { from: 165, to: 58, glide: 0.22, peak: 0.9 * v, decay: 0.55 });
  tone(t, { type: 'triangle', from: 320, to: 110, glide: 0.08, peak: 0.25 * v, decay: 0.18 });
  burst(t, { type: 'lowpass', freq: 700, peak: 0.35 * v, decay: 0.07 });
}
/** The bamboo stick on the tight side: a dry crack with a short ring. */
function tak(t, v = 1) {
  burst(t, { freq: 2600 + Math.random() * 500, q: 1.4, peak: 0.45 * v, decay: 0.06 });
  tone(t, { type: 'triangle', from: 470, to: 330, glide: 0.06, peak: 0.22 * v, decay: 0.12 });
}
/** Kansor: a struck bronze plate. Inharmonic partials that shimmer and fade. */
function kansor(t, v = 1) {
  for (const [f, a, d] of [[540, 0.10, 0.5], [1290, 0.09, 0.45], [2110, 0.07, 0.35], [2960, 0.05, 0.3], [3720, 0.04, 0.25]]) {
    tone(t, { from: f * (1 + (Math.random() - 0.5) * 0.01), peak: a * v, decay: d });
  }
  burst(t, { type: 'highpass', freq: 5000, peak: 0.08 * v, decay: 0.05 });
}
/** Ghanta: the small brass hand bell rung during arati. */
function ghanta(t, v = 1) {
  for (const [f, a, d] of [[1760, 0.06, 1.2], [2680, 0.04, 0.9], [4150, 0.025, 0.6]]) tone(t, { from: f, peak: a * v, decay: d });
}
/** Shankh: the conch. A breathy, slightly wavering horn that swells and fades. */
function shankh(t, dur = 2.6) {
  if (!ctx) return;
  const g = ctx.createGain(), f = ctx.createBiquadFilter(), lfo = ctx.createOscillator(), lg = ctx.createGain();
  f.type = 'lowpass'; f.frequency.value = 1400; f.Q.value = 2;
  lfo.frequency.value = 5.2; lg.gain.value = 3; lfo.connect(lg);
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(0.22, t + 0.45);
  g.gain.setValueAtTime(0.22, t + dur - 0.5);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  for (const det of [0, 4, -3]) {
    const o = ctx.createOscillator();
    o.type = 'sawtooth'; o.frequency.setValueAtTime(233 + det, t); o.frequency.linearRampToValueAtTime(247 + det, t + dur);
    lg.connect(o.frequency); o.connect(f); o.start(t); o.stop(t + dur + 0.05);
  }
  burst(t, { freq: 900, q: 0.7, peak: 0.05, decay: dur * 0.8 });
  f.connect(g); g.connect(master);
  lfo.start(t); lfo.stop(t + dur + 0.05);
}

const emit = (kind, t) => { const ms = Math.max(0, (t - ctx.currentTime) * 1000); setTimeout(() => listeners.forEach((fn) => fn(kind)), ms); };
function playStep(s, t) {
  const p = STATIONS[station], fill = bar % 4 === 3, ch = (str) => str[s] || '.';
  const human = () => 0.75 + Math.random() * 0.25, jitter = () => (Math.random() - 0.5) * 0.008;
  const b = ch(p.B), k = ch(p.K), g = ch(p.G), tk = fill ? ch(p.F) : ch(p.T);
  if (b !== '.') { dhyang(t + jitter(), (b === 'X' ? 1 : 0.75) * human()); emit('boom', t); }
  if (tk !== '.') { tak(t + jitter(), (tk === 'X' ? 1 : 0.7) * human()); emit('tak', t); }
  else if (!fill && Math.random() < 0.06) tak(t, 0.35); // the odd grace stroke a real dhaki adds
  if (k !== '.') kansor(t + jitter(), 0.8 * human());
  if (g !== '.') ghanta(t, human());
}
function schedule() {
  const p = STATIONS[station], dt = 60 / p.bpm / 4;
  while (nextTime < ctx.currentTime + 0.12) {
    if (step === 0 && p.shankh && bar % p.shankh === 0) shankh(nextTime, 2.4);
    playStep(step, nextTime);
    nextTime += dt; step = (step + 1) % 16; if (!step) bar++;
  }
}

export function play(id) {
  if (!STATIONS[id] || !audio()) return false;
  const fresh = !timer || station !== id;
  station = id;
  if (fresh) { step = 0; bar = 0; nextTime = ctx.currentTime + 0.08; }
  if (!timer) timer = setInterval(schedule, 25);
  listeners.forEach((fn) => fn('state'));
  return true;
}
export function stop() {
  clearInterval(timer); timer = null;
  listeners.forEach((fn) => fn('state'));
}
export const playing = () => !!timer;
export const current = () => station;
export const onBeat = (fn) => { listeners.add(fn); return () => listeners.delete(fn); };

/** Play one stroke by hand (the tappable dhak): left half is the bass side, right half the stick. */
export function strike(side) {
  if (!audio()) return;
  const t = ctx.currentTime + 0.005;
  side === 'boom' ? dhyang(t, 1) : tak(t, 1);
  listeners.forEach((fn) => fn(side));
}
export function blowShankh() { if (audio()) shankh(ctx.currentTime + 0.03, 2.8); }
