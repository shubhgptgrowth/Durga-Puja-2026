/* Tap sounds: a single dhak stroke and the shankh, real recordings (app/audio, Wikimedia Commons).
 * Web Audio, so taps are instant and overlap like a real dhaki's. The context starts inside the first tap. */
import { track } from './analytics.js';

let ctx = null;
const buffers = {};
const SOUNDS = { dhak: 'audio/dhak_hit.mp3', shankh: 'audio/shankh.mp3' };

function ensure() {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    ctx = new AC();
  }
  if (ctx.state === 'suspended') ctx.resume();
  return ctx;
}
function load(name) {
  buffers[name] ||= fetch(SOUNDS[name]).then((r) => r.arrayBuffer()).then((b) => new Promise((res, rej) => ctx.decodeAudioData(b, res, rej)));
  return buffers[name];
}
/** Warm the samples up (after the first tap) so the next one plays with no delay. */
export function preload() { if (ensure()) Object.keys(SOUNDS).forEach((n) => load(n).catch(() => {})); }

/** Play a sound; `vary` nudges pitch and level a little so repeated taps sound like a hand, not a machine. */
export async function play(name, { vary = true } = {}) {
  if (!ensure() || !SOUNDS[name]) return;
  track('sfx', { d: name });
  try {
    const buf = await load(name);
    const src = ctx.createBufferSource(), g = ctx.createGain();
    src.buffer = buf;
    if (vary) { src.playbackRate.value = 0.94 + Math.random() * 0.12; g.gain.value = 0.8 + Math.random() * 0.2; }
    src.connect(g); g.connect(ctx.destination);
    src.start();
  } catch { /* offline before the sample was cached */ }
}
