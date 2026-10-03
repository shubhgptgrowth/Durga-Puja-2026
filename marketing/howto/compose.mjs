// Turns the raw recordings and screenshots from record.mjs into Instagram-ready files.
//
//   node marketing/howto/record.mjs  <outDir>      # 1. record (needs Playwright's Chromium)
//   node marketing/howto/compose.mjs <outDir> [--only=quiet,carousel,story]   # 2. compose (needs ffmpeg)
//
// Writes into <outDir>:
//   reels/<n>-<id>.mp4      1080×1920, H.264, 30 fps, no audio: brand background, the phone recording in a
//                           rounded frame, a hook line on top, step captions, and a 3 s end card.
//   carousel/slide-NN.jpg   1080×1350 how-to carousel (hook, one slide per feature, CTA)
//   story/story-N.jpg       1080×1920 story frames
// Text overlays are HTML rendered by Playwright to transparent PNGs (so Bengali and emoji render), then
// composited with ffmpeg overlay filters gated by enable='between(t,a,b)'. Edit the copy in REELS,
// SLIDES and STORIES below. Never put the app's web address on an overlay: use "Link in bio".
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, mkdirSync, existsSync, rmSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import path from 'node:path';

const args = process.argv.slice(2);
const out = path.resolve(args.find((a) => !a.startsWith('--')) || 'howto-out');
const only = (args.find((a) => a.startsWith('--only=')) || '').slice(7).split(',').filter(Boolean);
const want = (id) => !only.length || only.includes(id);
const FFMPEG = process.env.FFMPEG || 'ffmpeg';
const raw = path.join(out, 'raw'), tmp = path.join(raw, 'overlays');
for (const d of ['reels', 'carousel', 'story', tmp]) mkdirSync(path.isAbsolute(d) ? d : path.join(out, d), { recursive: true });

const HANDLE = '@pujoparikrama.guide';
const W = 1080, H = 1920;
// Phone screen placement inside the 1080×1920 reel (the recording is 1170×2280).
const SCR = { w: 600, h: Math.round(600 * 2280 / 1170 / 2) * 2, x: 240, y: 560, r: 44, bezel: 14 };
const END_S = 3;

const REELS = [
  { id: 'quiet', n: 1, hook: 'Find when a pandal is<br><em>least crowded</em>', bn: 'কখন ভিড় কম, এক নজরে' },
  { id: 'route', n: 2, hook: 'Plan your whole night<br>in <em>3 taps</em>', bn: 'তিন ধাপে পুরো রাতের রুট' },
  { id: 'transport', n: 3, hook: 'Nearest <em>metro, auto & food</em><br>for any pandal', bn: 'মেট্রো, অটো, খাবার: সব এক জায়গায়' },
  { id: 'live', n: 4, hook: 'Check in & see<br><em>live crowds</em>', bn: 'কোথায় এখন ভিড়, দেখে নিন', note: 'Demo data shown' },
  { id: 'mypujo', n: 5, hook: 'Your <em>Pujo card</em>: steps,<br>pandals, badges', bn: 'আপনার পুজো কার্ড, সোজা স্টোরিতে', note: 'Demo data shown' },
  { id: 'bangla', n: 6, hook: 'Works in <em>বাংলা</em> too', bn: 'এক ট্যাপে পুরো অ্যাপ বাংলায়' },
  { id: 'whatsapp', n: 7, hook: 'Send a pandal to your<br><em>family WhatsApp group</em>', bn: 'পরিবারের গ্রুপে পাঠিয়ে দিন' },
];

const FONT = `Poppins, "Hind Siliguri", "Noto Sans Bengali", "Noto Color Emoji", sans-serif`;
const BG = `background:linear-gradient(160deg,#9F1239 0%,#B91C1C 55%,#7C2D12 100%)`;
const RINGS = `<div style="position:absolute;right:-260px;top:-260px;width:900px;height:900px;border-radius:50%;box-shadow:0 0 0 6px rgba(253,230,138,.16),0 0 0 110px transparent,0 0 0 116px rgba(253,230,138,.12),0 0 0 220px transparent,0 0 0 226px rgba(253,230,138,.08)"></div>`;
const CSS = `*{box-sizing:border-box;margin:0}html,body{background:transparent}body{font-family:${FONT};color:#fff;overflow:hidden;position:relative}
em{font-style:normal;color:#FDE68A}.bn{font-family:"Hind Siliguri","Noto Sans Bengali",sans-serif}`;
const page0 = (w, h, body, extra = '') => `<!doctype html><html><head><meta charset="utf-8"><style>${CSS}${extra}</style></head><body style="width:${w}px;height:${h}px">${body}</body></html>`;

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined });
const page = await browser.newPage({ deviceScaleFactor: 1 });
async function png(file, w, h, html, { transparent = true, jpeg = false } = {}) {
  await page.setViewportSize({ width: w, height: h });
  const f = path.join(tmp, path.basename(file) + '.html'); writeFileSync(f, html);
  await page.goto('file://' + f); await page.evaluate(() => document.fonts.ready); await page.waitForTimeout(80);
  await page.screenshot({ path: file, omitBackground: transparent && !jpeg, ...(jpeg ? { type: 'jpeg', quality: 92 } : {}) });
}
const ff = (a) => execFileSync(FFMPEG, ['-hide_banner', '-loglevel', 'error', '-y', ...a], { stdio: 'inherit' });

/* ---------------- reel layers ---------------- */
// The frame layer is the whole background with a rounded transparent hole where the screen goes.
const frameLayer = (note) => page0(W, H, `
  <svg width="${W}" height="${H}" style="position:absolute;inset:0">
    <defs><linearGradient id="g" x1="0" y1="0" x2="0.56" y2="1"><stop offset="0" stop-color="#9F1239"/><stop offset=".55" stop-color="#B91C1C"/><stop offset="1" stop-color="#7C2D12"/></linearGradient>
      <mask id="m"><rect width="${W}" height="${H}" fill="#fff"/><rect x="${SCR.x}" y="${SCR.y}" width="${SCR.w}" height="${SCR.h}" rx="${SCR.r}" fill="#000"/></mask>
      <filter id="s" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="18" stdDeviation="22" flood-color="#000" flood-opacity=".45"/></filter></defs>
    <g mask="url(#m)">
      <rect width="${W}" height="${H}" fill="url(#g)"/>
      <g fill="none" stroke="rgba(253,230,138,.14)" stroke-width="6">${[300, 410, 520].map((r) => `<circle cx="${W + 40}" cy="40" r="${r}"/>`).join('')}</g>
      <rect x="${SCR.x - SCR.bezel}" y="${SCR.y - SCR.bezel}" width="${SCR.w + 2 * SCR.bezel}" height="${SCR.h + 2 * SCR.bezel}" rx="${SCR.r + SCR.bezel}" fill="#1C1917" filter="url(#s)"/>
    </g>
  </svg>
  <div style="position:absolute;left:0;right:0;top:${SCR.y + SCR.h + SCR.bezel + 22}px;text-align:center;font-size:30px;font-weight:600;color:#FDE68A">🪔 Pujo Parikrama · ${HANDLE}${note ? `<span style="color:#fff;opacity:.8;font-size:24px;font-weight:500"> · ${note}</span>` : ''}</div>`);
const hookLayer = (r) => page0(W, H, `<div style="position:absolute;left:60px;right:60px;top:150px;text-align:center">
    <div style="font-size:28px;font-weight:700;letter-spacing:2px;color:#FDE68A;opacity:.95">HOW TO · PUJO PARIKRAMA</div>
    <div style="font-size:${r.hook.length > 55 ? 58 : 64}px;font-weight:800;line-height:1.1;margin-top:14px;text-shadow:0 3px 14px rgba(0,0,0,.25)">${r.hook}</div>
    <div class="bn" style="font-size:32px;font-weight:600;margin-top:10px;opacity:.92">${r.bn}</div></div>`);
const capLayer = (text, i) => page0(W, H, `<div style="position:absolute;left:40px;right:40px;top:${SCR.y - 18 - 104}px;height:104px;display:flex;align-items:center;justify-content:center">
    <div style="background:#FDE68A;color:#7F1D1D;font-weight:800;font-size:${text.length > 44 ? 31 : 36}px;line-height:1.15;padding:16px 30px;border-radius:28px;text-align:center;box-shadow:0 8px 24px rgba(0,0,0,.3);max-width:1000px">
    <span style="display:inline-block;background:#9F1239;color:#FDE68A;border-radius:50%;width:44px;height:44px;line-height:44px;font-size:24px;margin-right:12px;vertical-align:3px">${i + 1}</span>${text}</div></div>`);
const endCard = () => page0(W, H, `<div style="position:absolute;inset:0;${BG}"></div>${RINGS}
  <div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:0 80px">
    <img src="${path.resolve(path.dirname(new URL(import.meta.url).pathname), '../../app/icons/icon-512.png')}" style="width:190px;height:190px;border-radius:44px;box-shadow:0 12px 40px rgba(0,0,0,.35)">
    <div style="font-size:84px;font-weight:800;margin-top:48px;line-height:1.05">Pujo Parikrama</div>
    <div style="font-size:36px;margin-top:14px;opacity:.95">Kolkata Durga Puja 2026 guide</div>
    <div style="font-size:46px;font-weight:700;margin-top:70px;color:#FDE68A">Free · No sign-up</div>
    <div style="margin-top:44px;background:#FDE68A;color:#7F1D1D;font-weight:800;font-size:52px;border-radius:999px;padding:28px 70px">Link in bio</div>
    <div style="font-size:42px;font-weight:700;margin-top:44px">${HANDLE}</div>
    <div class="bn" style="font-size:34px;margin-top:20px;opacity:.9">ফ্রি · সাইন-আপ লাগে না · বাংলা ও ইংরেজিতে</div></div>`);

async function composeReel(r) {
  const dir = path.join(raw, r.id);
  if (!existsSync(path.join(dir, 'cues.json'))) { console.warn('  no recording for', r.id); return; }
  const { duration: D, cues } = JSON.parse(readFileSync(path.join(dir, 'cues.json'), 'utf8'));
  const L = (n) => path.join(tmp, `${r.id}-${n}.png`);
  await png(L('frame'), W, H, frameLayer(r.note));
  await png(L('hook'), W, H, hookLayer(r));
  await png(L('end'), W, H, endCard(), { transparent: false });
  for (const [i, c] of cues.entries()) await png(L('cap' + i), W, H, capLayer(c.text, i));
  const inputs = ['-f', 'concat', '-safe', '0', '-i', path.join(dir, 'frames.txt'),
    '-loop', '1', '-framerate', '30', '-t', String(D), '-i', L('frame'),
    '-loop', '1', '-framerate', '30', '-t', String(D), '-i', L('hook'),
    ...cues.flatMap((_, i) => ['-loop', '1', '-framerate', '30', '-t', String(D), '-i', L('cap' + i)]),
    '-loop', '1', '-framerate', '30', '-t', String(END_S), '-i', L('end')];
  const endIdx = 3 + cues.length;
  const f = [
    `color=c=#1C1917:s=${W}x${H}:r=30:d=${D}[base]`,
    `[0:v]fps=30,scale=${SCR.w}:${SCR.h}:flags=lanczos,setsar=1[scr]`,
    `[base][scr]overlay=${SCR.x}:${SCR.y}:shortest=1[v0]`,
    `[v0][1:v]overlay=0:0[v1]`,
    `[v1][2:v]overlay=0:0:enable='between(t,0,${D})'[v2]`,
  ];
  let last = 'v2';
  cues.forEach((c, i) => {
    const a = c.t, b = i + 1 < cues.length ? cues[i + 1].t : D;
    f.push(`[${last}][${3 + i}:v]overlay=0:0:enable='between(t,${a.toFixed(3)},${b.toFixed(3)})'[c${i}]`); last = 'c' + i;
  });
  f.push(`[${last}]trim=duration=${D},setpts=PTS-STARTPTS,format=yuv420p,settb=1/30[main]`);
  f.push(`[${endIdx}:v]fps=30,format=yuv420p,setsar=1,settb=1/30[endv]`);
  f.push(`[main][endv]xfade=transition=fade:duration=0.4:offset=${(D - 0.4).toFixed(3)}[outv]`);
  const file = path.join(out, 'reels', `${r.n}-${r.id}.mp4`);
  ff([...inputs, '-filter_complex', f.join(';'), '-map', '[outv]', '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-profile:v', 'high',
    '-pix_fmt', 'yuv420p', '-r', '30', '-movflags', '+faststart', file]);
  console.log(`  ${path.basename(file)}: ${(D - 0.4 + END_S).toFixed(1)} s`);
}

/* ---------------- carousel (1080×1350) and story (1080×1920) ---------------- */
const shot = (n) => 'file://' + path.join(raw, 'shots', n + '.png');
const phone = (src, w, { tilt = 0 } = {}) => `<div style="width:${w + 24}px;padding:12px;background:#1C1917;border-radius:${Math.round(w * 0.1)}px;box-shadow:0 24px 60px rgba(0,0,0,.45);transform:rotate(${tilt}deg)">
  <img src="${src}" style="display:block;width:${w}px;border-radius:${Math.round(w * 0.08)}px"></div>`;
const brandTop = `<div style="font-size:30px;font-weight:700;color:#FDE68A">🪔 Pujo Parikrama 2026</div>`;
const SLIDES = [
  { hook: true },
  { shot: 'home', t: 'Start with what you want to do', s: 'Pandals near me, a route, must-sees, food, parking, photos: one tap each.' },
  { shot: 'quiet-hours', t: 'Go when it’s quiet', s: 'Every pandal has an hour-by-hour crowd chart and its quietest hours.' },
  { shot: 'getting-there', t: 'Get there without the hassle', s: 'Nearest metro, shared autos, parking and food within walking distance.' },
  { shot: 'route-result', t: 'Your whole night in 3 taps', s: 'Pick areas → pick your start → get a timed walking route with food stops.' },
  { shot: 'live-list', t: 'See where the crowd is now', s: 'Check in at a pandal; live check-ins show what’s packed right now.', demo: true },
  { shot: 'me', t: 'Your Pujo card', s: 'Steps, pandals and badges, and a story-size card to share.', demo: true },
  { shot: 'home-bn', t: 'বাংলাতেও চলে', s: 'Switch the whole app to Bengali in one tap. Works offline once opened.' },
  { cta: true },
];
function slideHtml(sl, i, n) {
  const W2 = 1080, H2 = 1350, bg = `<div style="position:absolute;inset:0;${BG}"></div>${RINGS}`;
  if (sl.hook) return page0(W2, H2, `${bg}<div style="position:absolute;inset:0;padding:80px 70px;display:flex;flex-direction:column">${brandTop}
    <div style="display:flex;gap:40px;align-items:center;margin-top:50px">
      <div style="flex:1"><div style="font-size:92px;font-weight:800;line-height:1.02">Pandal hopping, <em>sorted.</em></div>
        <div style="font-size:46px;font-weight:700;margin-top:30px">Here’s how 👇</div>
        <div class="bn" style="font-size:36px;margin-top:26px;opacity:.92">ঠাকুর দেখার সব প্ল্যান, এক অ্যাপে</div>
        <div style="font-size:30px;margin-top:40px;opacity:.9;line-height:1.4">Free Kolkata Durga Puja guide<br>Swipe to see how it works →</div></div>
      <div style="flex:0 0 auto;margin-right:-10px">${phone(shot('home'), 360, { tilt: 4 })}</div></div></div>`);
  if (sl.cta) return page0(W2, H2, `${bg}<div style="position:absolute;inset:0;padding:90px 80px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center">
    <img src="${path.resolve(path.dirname(new URL(import.meta.url).pathname), '../../app/icons/icon-512.png')}" style="width:170px;height:170px;border-radius:40px;box-shadow:0 12px 40px rgba(0,0,0,.35)">
    <div style="font-size:78px;font-weight:800;margin-top:40px;line-height:1.05">Save this for <em>Saptami</em></div>
    <div style="font-size:40px;margin-top:26px;opacity:.95">107 pandals · quiet hours · metro & auto · food · parking</div>
    <div style="font-size:44px;font-weight:700;margin-top:50px;color:#FDE68A">Free · No sign-up</div>
    <div style="margin-top:36px;background:#FDE68A;color:#7F1D1D;font-weight:800;font-size:50px;border-radius:999px;padding:26px 66px">Link in bio</div>
    <div style="font-size:40px;font-weight:700;margin-top:36px">${HANDLE}</div>
    <div class="bn" style="font-size:32px;margin-top:18px;opacity:.9">ফ্রি · বাংলা ও ইংরেজিতে · অফলাইনেও চলে</div></div>`);
  return page0(W2, H2, `${bg}<div style="position:absolute;inset:0;padding:70px 70px 0;display:flex;gap:50px">
    <div style="flex:1;display:flex;flex-direction:column;padding-top:10px">${brandTop}
      <div style="margin-top:auto;margin-bottom:auto">
        <div style="width:84px;height:84px;border-radius:50%;background:#FDE68A;color:#7F1D1D;font-weight:800;font-size:44px;display:flex;align-items:center;justify-content:center">${i}</div>
        <div class="${/[ঀ-৿]/.test(sl.t) ? 'bn' : ''}" style="font-size:64px;font-weight:800;line-height:1.08;margin-top:30px">${sl.t}</div>
        <div style="font-size:36px;line-height:1.38;margin-top:26px;opacity:.95">${sl.s}</div>
        ${sl.demo ? `<div style="font-size:22px;margin-top:22px;opacity:.75">Numbers shown are demo data</div>` : ''}
      </div>
      <div style="font-size:26px;opacity:.85;margin-bottom:60px">${i}/${n - 2} · ${HANDLE}</div></div>
    <div style="flex:0 0 auto;align-self:flex-end;margin-bottom:-170px">${phone(shot(sl.shot), 470)}</div></div>`);
}
const STORIES = [
  { shot: 'quiet-hours', t: 'Go when it’s <em>quiet</em>', s: 'Crowd by hour for every pandal' },
  { shot: 'route-result', t: 'Your night in <em>3 taps</em>', s: 'Areas → start → timed route' },
  { shot: 'live-list', t: 'See <em>live crowds</em>', s: 'Check-ins from people at the pandal', demo: true },
  { shot: 'me', t: 'Share your <em>Pujo card</em>', s: 'Steps, pandals, badges', demo: true, cta: true },
];
const storyHtml = (s, i) => page0(1080, 1920, `<div style="position:absolute;inset:0;${BG}"></div>${RINGS}
  <div style="position:absolute;inset:0;padding:200px 70px 0;display:flex;flex-direction:column;align-items:center;text-align:center">
    ${brandTop}
    <div style="font-size:76px;font-weight:800;line-height:1.08;margin-top:22px">${s.t}</div>
    <div style="font-size:38px;margin-top:14px;opacity:.95">${s.s}</div>
    <div style="margin-top:40px">${phone(shot(s.shot), 470)}</div></div>
  ${s.demo ? `<div style="position:absolute;left:0;right:0;top:150px;text-align:center;font-size:22px;opacity:.7">Demo data</div>` : ''}
  <div style="position:absolute;left:0;right:0;bottom:0;height:300px;background:linear-gradient(180deg,rgba(127,29,29,0),rgba(124,45,18,.6))"></div>
  <div style="position:absolute;left:0;right:0;bottom:200px;text-align:center">
    ${s.cta ? `<span style="background:#FDE68A;color:#7F1D1D;font-weight:800;font-size:46px;border-radius:999px;padding:24px 60px">Link in bio</span>` : `<span style="font-size:36px;font-weight:700;color:#FDE68A">${i + 1}/4 · tap for more →</span>`}
    <div style="font-size:34px;font-weight:700;margin-top:36px">Free · No sign-up · ${HANDLE}</div></div>`);

try {
  for (const r of REELS) if (want(r.id)) { console.log('reel', r.id); await composeReel(r); }
  if (want('carousel')) {
    rmSync(path.join(out, 'carousel'), { recursive: true, force: true }); mkdirSync(path.join(out, 'carousel'));
    for (const [i, sl] of SLIDES.entries()) await png(path.join(out, 'carousel', `slide-${String(i + 1).padStart(2, '0')}.jpg`), 1080, 1350, slideHtml(sl, i, SLIDES.length), { jpeg: true });
    console.log(`  carousel: ${SLIDES.length} slides`);
  }
  if (want('story')) {
    for (const [i, s] of STORIES.entries()) await png(path.join(out, 'story', `story-${i + 1}.jpg`), 1080, 1920, storyHtml(s, i), { jpeg: true });
    console.log(`  story: ${STORIES.length} frames`);
  }
} finally { await browser.close(); }
