// "How to use the app" screen recordings and screenshots for Instagram.
//
//   node marketing/howto/record.mjs [outDir] [--only=quiet,route,...] [--shots-only|--reels-only]
//   then: node marketing/howto/compose.mjs [outDir]       (reels → MP4, carousel + story JPEGs)
//
// outDir defaults to ./howto-out. For every reel this writes <outDir>/raw/<id>/: JPEG frames from
// a Chrome screencast of a 390×760 phone viewport at 3× (1170×2280), frames.txt (an ffmpeg concat
// list with each frame's real duration) and cues.json (the step captions and when they start).
// Screenshots for the carousel/story go to <outDir>/raw/shots/*.png.
//
// The app runs against the in-memory fake Supabase from tests/e2e (seeded with demo check-ins), so
// counts and "live" numbers are DEMO data. The phone clock is set to Saptami (18 Oct 2026, 7:10 pm
// IST) so crowd charts and "today" read like a pujo evening. Re-run after app changes; nothing
// here edits the app. Things the sandbox can't reach are stubbed so frames don't look broken:
// raster map tiles get a flat land-coloured tile, and the Wikimedia photo galleries are hidden.
// Text uses Roboto + Noto Sans Bengali (an Android-like look); install them as system fonts first
// if they are missing (fc-list | grep -i bengali), or Bengali renders as boxes.
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { readFileSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import zlib from 'node:zlib';
import { startFakeSupabase } from '../../tests/e2e/fake-supabase.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const args = process.argv.slice(2);
const out = path.resolve(args.find((a) => !a.startsWith('--')) || 'howto-out');
const only = (args.find((a) => a.startsWith('--only=')) || '').slice(7).split(',').filter(Boolean);
const doShots = !args.includes('--reels-only'), doReels = !args.includes('--shots-only');
const guidePath = path.join(root, 'app/data/guide.json');
const G = JSON.parse(readFileSync(guidePath, 'utf8'));
const P = Object.fromEntries([...G.pandals, ...G.food].map((p) => [p.id, p]));

const VIEW = { width: 390, height: 760 }, DSF = 3;
const NOW = new Date('2026-10-18T19:10:00+05:30');   // Saptami evening
const TODAY = '2026-10-18';

/* ---------------- fake backend with demo numbers ---------------- */
const fake = await startFakeSupabase({ guidePath });
{
  const istDay = (d = new Date()) => new Date(d.getTime() + 5.5 * 3600e3).toISOString().slice(0, 10);
  let seed = 7; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const now = Date.now(), day = istDay();
  for (const p of G.pandals) {
    const pop = p.popularity, total = Math.round(pop ** 3 * (1.5 + rnd() * 1.5)), lastHour = pop >= 4 ? Math.round(pop ** 2 * (0.4 + rnd() * 0.9)) : Math.round(rnd() * 2);
    for (let i = 0; i < total; i++) {
      const recent = i < lastHour, at = recent ? now - rnd() * 3500e3 : now - (1 + rnd() * 30) * 3600e3;
      fake.db.visits.push({ user: 'demo' + i, place_id: p.id, day: recent || i % 2 ? day : istDay(new Date(at)), at });
    }
  }
  for (const f of G.food) for (let i = 0, n = Math.round(8 + rnd() * 30); i < n; i++) fake.db.visits.push({ user: 'demo' + i, place_id: f.id, day, at: now - rnd() * 20 * 3600e3 });
}
const backend = { url: fake.url, anonKey: fake.anonKey };

/* ---------------- static server ---------------- */
const port = 8300 + Math.floor(Math.random() * 500);
const server = spawn('python3', ['-m', 'http.server', '-d', path.join(root, 'app'), String(port)], { stdio: 'ignore' });
const base = `http://127.0.0.1:${port}/`;
for (let i = 0; i < 50; i++) { try { await fetch(base); break; } catch { await new Promise((r) => setTimeout(r, 100)); } }

// A flat 256×256 land-coloured PNG stands in for raster map tiles (the tile CDN is unreachable here).
function flatPng(w, h, [r, g, b]) {
  const crcT = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
  const crc = (buf) => { let c = 0xffffffff; for (const x of buf) c = crcT[(c ^ x) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  const chunk = (type, data) => { const len = Buffer.alloc(4); len.writeUInt32BE(data.length); const td = Buffer.concat([Buffer.from(type), data]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(td)); return Buffer.concat([len, td, c]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  const row = Buffer.concat([Buffer.from([0]), Buffer.alloc(w * 3).map((_, i) => [r, g, b][i % 3])]);
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(Buffer.concat(Array(h).fill(row)))), chunk('IEND', Buffer.alloc(0))]);
}
const TILE = flatPng(256, 256, [238, 234, 226]);

/* ---------------- demo state on the phone ---------------- */
const at = (id) => ({ latitude: P[id].lat, longitude: P[id].lng, accuracy: 12 });
const ts = (hhmm, date = TODAY) => new Date(`${date}T${hhmm}:00+05:30`).getTime();
// A believable Saptami so far: north in the afternoon, south in the evening (for the "My pujo" reel).
const MY_DAY = {
  checkins: { bagbazar: ts('15:05'), kumartuli_park: ts('15:50'), sovabazar_rajbari: ts('16:30'), md_ali_park: ts('17:25'), college_square: ts('17:55'), tridhara: ts('18:40'), badamtala: ts('19:00') },
  history: {
    [TODAY]: { m: 10850, ms: 2.6 * 3600e3, steps: 14862, pandals: ['bagbazar', 'kumartuli_park', 'sovabazar_rajbari', 'md_ali_park', 'college_square', 'tridhara', 'badamtala'], foods: ['coffee_house'] },
    '2026-10-17': { m: 6200, ms: 1.5 * 3600e3, steps: 8410, pandals: [], foods: [] },
  },
};
function seedFor(kind) {
  const ls = { 'pp:introDone': true, 'pp:dataVersion': JSON.stringify(G.meta.version), 'pp:day': JSON.stringify('saptami') };
  if (kind === 'me') {
    const food = G.food.filter((f) => ['north', 'central', 'south_lakemarket'].includes(f.zone)).slice(0, 3).map((f) => f.id);
    const hist = structuredClone(MY_DAY.history); hist[TODAY].foods = food;
    ls['pp:checkins'] = Object.fromEntries(Object.entries(MY_DAY.checkins).map(([id, t]) => [id, { ts: t, how: 'gps', community: true }]));
    ls['pp:history'] = hist;
  }
  return Object.fromEntries(Object.entries(ls).map(([k, v]) => [k, typeof v === 'string' ? v : JSON.stringify(v)]));
}

// Tap ripple (viewers need to see where the finger went), fonts, and hiding the unreachable photo galleries.
const INJECT = `
  :root { --font: Roboto, "Noto Sans Bengali", system-ui, sans-serif !important; }
  body { font-family: Roboto, "Noto Sans Bengali", sans-serif; }
  .sheet .gallery, .sheet .gallery + .credit { display: none !important; }
  .tap-dot { position: fixed; width: 46px; height: 46px; margin: -23px 0 0 -23px; border-radius: 50%; background: rgba(250, 204, 21, .45);
    border: 3px solid rgba(255,255,255,.95); box-shadow: 0 0 0 2px rgba(127,29,29,.35); pointer-events: none; z-index: 2147483647;
    animation: tapdot .7s ease-out forwards; }
  @keyframes tapdot { 0% { transform: scale(.5); opacity: 1 } 60% { transform: scale(1.1); opacity: .9 } 100% { transform: scale(1.5); opacity: 0 } }
  .demo-overlay { position: fixed; inset: 0; z-index: 2147483600; background: rgba(0,0,0,.72); display: flex; align-items: center; justify-content: center; padding: 18px; animation: fadein .3s ease-out; }
  @keyframes fadein { from { opacity: 0 } to { opacity: 1 } }
`;
function initScript({ seed, css, cfg }) {
  try { if (!localStorage.getItem('pp:__seeded')) { for (const [k, v] of Object.entries(seed)) localStorage.setItem(k, v); localStorage.setItem('pp:__seeded', '1'); } } catch {}
  window.PP_CONFIG = { community: cfg };
  const addStyle = () => { const s = document.createElement('style'); s.textContent = css; document.head.append(s); };
  if (document.head) addStyle(); else document.addEventListener('DOMContentLoaded', addStyle);
  addEventListener('pointerdown', (e) => {
    const d = document.createElement('div'); d.className = 'tap-dot'; d.style.left = e.clientX + 'px'; d.style.top = e.clientY + 'px';
    document.documentElement.append(d); setTimeout(() => d.remove(), 800);
  }, true);
}

/* ---------------- browser + recorder ---------------- */
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined });

async function newPhone({ kind = 'default', geo = 'tridhara' } = {}) {
  const ctx = await browser.newContext({
    viewport: VIEW, deviceScaleFactor: DSF, isMobile: true, hasTouch: true, locale: 'en-IN', timezoneId: 'Asia/Kolkata',
    userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36',
    geolocation: at(geo), permissions: ['geolocation', 'clipboard-read', 'clipboard-write'], acceptDownloads: true,
  });
  await ctx.clock.install({ time: NOW });
  await ctx.route(/basemaps\.cartocdn\.com|tile\.openstreetmap/, (r) => r.fulfill({ status: 200, contentType: 'image/png', body: TILE }));
  await ctx.route(/wikimedia\.org|wa\.me|whatsapp/, (r) => r.abort());
  await ctx.addInitScript(initScript, { seed: seedFor(kind), css: INJECT, cfg: backend });
  let page0 = null;
  ctx.on('page', (p) => { if (page0 && p !== page0) p.close().catch(() => {}); });
  page0 = await ctx.newPage();
  page0.on('pageerror', (e) => console.warn('  pageerror:', e.message));
  await page0.goto(base);
  await page0.waitForSelector('.hero');
  await page0.evaluate(() => document.fonts.ready);
  await page0.waitForTimeout(1200);   // first stats sync
  return { ctx, page: page0 };
}

/** Records a CDP screencast; `cap()` marks a caption change at the current time. */
async function recordReel(reel) {
  const dir = path.join(out, 'raw', reel.id);
  rmSync(dir, { recursive: true, force: true }); mkdirSync(dir, { recursive: true });
  const { ctx, page } = await newPhone(reel.phone || {});
  await reel.before?.(page, ctx);
  const cdp = await ctx.newCDPSession(page);
  const frames = [], cues = [];
  let t0 = null;
  cdp.on('Page.screencastFrame', async (f) => {
    const now = Date.now(); t0 ??= now;
    const file = `f${String(frames.length).padStart(5, '0')}.jpg`;
    writeFileSync(path.join(dir, file), Buffer.from(f.data, 'base64'));
    frames.push({ file, t: (now - t0) / 1000 });
    cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {});
  });
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: VIEW.width * DSF, maxHeight: VIEW.height * DSF, everyNthFrame: 1 });
  while (t0 == null) await page.waitForTimeout(20);
  const el = () => (Date.now() - t0) / 1000;
  const h = {
    page, ctx,
    cap: (text) => cues.push({ t: el(), text }),
    wait: (ms) => page.waitForTimeout(ms),
    async tap(sel, pause = 900) {
      const loc = page.locator(sel).first();
      await loc.scrollIntoViewIfNeeded();
      await loc.tap();
      await page.waitForTimeout(pause);
    },
    /** A ripple where the element is, without clicking (for <select> and the like). */
    async touch(sel) {
      const b = await page.locator(sel).first().boundingBox();
      if (b) await page.evaluate(([x, y]) => window.dispatchEvent(new PointerEvent('pointerdown', { clientX: x, clientY: y })), [b.x + b.width / 2, b.y + b.height / 2]);
      await page.waitForTimeout(350);
    },
    async type(sel, text) { await page.locator(sel).first().tap(); for (const ch of text) { await page.keyboard.type(ch); await page.waitForTimeout(110); } },
    /** Smoothly scroll the open sheet (or the page) so `sel` sits `offset` px from the top. */
    async scrollTo(sel, { ms = 900, offset = 70, inSheet = true } = {}) {
      await page.evaluate(async ([sel, ms, offset, inSheet]) => {
        const box = inSheet ? document.querySelector('#sheet') : document.scrollingElement;
        const target = document.querySelector(sel); if (!target) return;
        const from = box.scrollTop, top = inSheet ? target.getBoundingClientRect().top - box.getBoundingClientRect().top + from - offset : target.getBoundingClientRect().top + from - offset;
        const to = Math.max(0, Math.min(top, box.scrollHeight - box.clientHeight));
        const t0 = performance.now();
        await new Promise((res) => { const step = (now) => { const k = Math.min(1, (now - t0) / ms), e = k < .5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2; box.scrollTop = from + (to - from) * e; k < 1 ? requestAnimationFrame(step) : res(); }; requestAnimationFrame(step); });
      }, [sel, ms, offset, inSheet]);
      await page.waitForTimeout(150);
    },
    async overlay(html, ms) {
      await page.evaluate((html) => { const d = document.createElement('div'); d.className = 'demo-overlay'; d.innerHTML = html; document.body.append(d); }, html);
      await page.waitForTimeout(ms);
    },
  };
  await page.waitForTimeout(600);
  await reel.run(h);
  const end = el();
  await cdp.send('Page.stopScreencast').catch(() => {});
  await page.waitForTimeout(200);
  // concat list: each frame lasts until the next one arrives
  const lines = ['ffconcat version 1.0'];
  frames.forEach((f, i) => { const d = (i + 1 < frames.length ? frames[i + 1].t : end) - f.t; if (d > 0) lines.push(`file ${f.file}`, `duration ${d.toFixed(4)}`); });
  lines.push(`file ${frames[frames.length - 1].file}`);
  writeFileSync(path.join(dir, 'frames.txt'), lines.join('\n') + '\n');
  writeFileSync(path.join(dir, 'cues.json'), JSON.stringify({ id: reel.id, duration: end, cues, frames: frames.length }, null, 2));
  console.log(`  ${reel.id}: ${end.toFixed(1)} s, ${frames.length} frames, ${cues.length} captions`);
  await ctx.close();
}

/* ---------------- the reels ---------------- */
const firstFamous = '#explorePanel .item[data-place]';
const REELS = [
  {
    id: 'quiet',
    async run(h) {
      h.cap('Tap “Must-see pandals”');
      await h.wait(1200);
      await h.tap('.task[data-q="famous"]', 1600);
      h.cap('Every pandal: crowd right now + best time to go');
      await h.wait(2600);
      h.cap('Tap a pandal');
      await h.tap(`#explorePanel .item[data-place="santosh_mitra"]`, 1300);
      h.cap('Crowd hour by hour, for the day you pick');
      await h.scrollTo('.sheet .hours', { offset: 120, ms: 1100 });
      await h.wait(2600);
      h.cap('Quietest hours + how long it takes inside');
      await h.wait(2400);
      await h.page.keyboard.press('Escape'); await h.wait(500);
      h.cap('Or sort the list by “Shortest queue now”');
      await h.touch('#sortSelect');
      await h.page.selectOption('#sortSelect', 'quiet');
      await h.page.evaluate(() => window.scrollTo(0, 0));
      await h.wait(2800);
    },
  },
  {
    id: 'route',
    async run(h) {
      h.cap('Tap “Plan my route”');
      await h.wait(1000);
      await h.tap('.task[data-q="plan"]', 1300);
      h.cap('Tap 1 · Pick the areas you want');
      await h.tap('#view-plan [data-pz="north"]', 700);
      await h.tap('#view-plan [data-pr="central"]', 1000);
      await h.tap('#planNext', 1200);
      h.cap('Tap 2 · Where and when you start');
      await h.tap('#planStartBtn', 900);
      await h.type('#pickSearch', 'shyam');
      await h.wait(500);
      await h.tap('[data-pick="t:shyambazar"]', 900);
      await h.touch('#planBudget');
      await h.page.selectOption('#planBudget', '360');
      await h.wait(900);
      h.cap('Tap 3 · Get your route');
      await h.tap('#planForm button[type="submit"]', 1600);
      h.cap('Pandal order, arrival times, steps & kcal');
      await h.wait(2200);
      h.cap('Food stops and metro legs on the way');
      await h.scrollTo('.timeline', { inSheet: false, offset: 140, ms: 1600 });
      await h.wait(1200);
      await h.page.evaluate(() => window.scrollBy({ top: 420, behavior: 'smooth' }));
      await h.wait(2400);
    },
  },
  {
    id: 'transport',
    phone: { geo: 'ekdalia' },
    async run(h) {
      h.cap('Search any pandal');
      await h.wait(800);
      await h.type('#homeSearch', 'ekdalia');
      await h.wait(700);
      await h.tap('#homeResults li[data-result="ekdalia"]', 1300);
      h.cap('Nearest metro + walking time');
      await h.scrollTo('.sheet h3.sh:nth-of-type(2)', { offset: 60, ms: 1100 });
      await h.wait(2300);
      h.cap('Autos that go there + parking nearby');
      await h.wait(2300);
      h.cap('Food you can walk to');
      await h.scrollTo('.sheet [data-food]', { offset: 120, ms: 1000 });
      await h.wait(1800);
      h.cap('Tap one: must-try dishes, hours, price');
      await h.tap('.sheet [data-food]', 1300);
      await h.scrollTo('.sheet h3.sh', { offset: 160, ms: 800 });
      await h.wait(2400);
    },
  },
  {
    id: 'live',
    phone: { geo: 'tridhara' },
    async run(h) {
      h.cap('At a pandal? Open it and tap “Check in”');
      await h.wait(600);
      await h.type('#homeSearch', 'tridhara');
      await h.wait(500);
      await h.tap('#homeResults li[data-result="tridhara"]', 1300);
      await h.tap('#visitBtn', 400);
      h.cap('GPS confirms you are really there');
      await h.wait(2600);
      h.cap('Live count: visits today + in the last hour');
      await h.scrollTo('.sheet .stat-row', { offset: 160, ms: 600 });
      await h.wait(2200);
      await h.page.keyboard.press('Escape'); await h.wait(400);
      h.cap('Map tab → sort by “Most check-ins now”');
      await h.tap('.tab[data-view="explore"]', 700);
      if (await h.page.locator('#modeBtn[data-to="list"]').count()) await h.tap('#modeBtn[data-to="list"]', 700);
      await h.touch('#sortSelect');
      await h.page.selectOption('#sortSelect', 'live');
      await h.wait(2600);
      h.cap('See where the crowd is before you go');
      await h.page.evaluate(() => window.scrollBy({ top: 300, behavior: 'smooth' }));
      await h.wait(2000);
    },
  },
  {
    id: 'mypujo',
    phone: { kind: 'me' },
    async run(h) {
      h.cap('Tap “My pujo”');
      await h.wait(800);
      await h.tap('.tab[data-view="me"]', 1300);
      h.cap('Steps, km and pandals for the day');
      await h.wait(2400);
      h.cap('Badges unlock as you go 🏅');
      await h.scrollTo('.badges', { inSheet: false, offset: 120, ms: 1200 });
      await h.wait(2200);
      h.cap('Tap “Share my Pujo card”');
      await h.scrollTo('#myCardBtn', { inSheet: false, offset: 200, ms: 900 });
      const dl = h.page.waitForEvent('download');
      await h.tap('#myCardBtn', 300);
      const file = path.join(out, 'raw', 'mypujo-card.png'); await (await dl).saveAs(file);
      const b64 = readFileSync(file).toString('base64');
      await h.wait(900);
      h.cap('A story-size card, ready for Instagram or WhatsApp Status');
      // Show the card as the phone's share preview would; crop the bottom line (it prints the app address).
      await h.overlay(`<div style="width:300px;height:${Math.round(300 * 1790 / 1080)}px;overflow:hidden;border-radius:16px;box-shadow:0 10px 40px rgba(0,0,0,.5)"><img src="data:image/png;base64,${b64}" style="width:300px;display:block"></div>`, 3600);
    },
  },
  {
    id: 'bangla',
    async run(h) {
      h.cap('Tap “বাংলা” at the top');
      await h.wait(1000);
      await h.tap('#langBtn', 1600);
      h.cap('The whole app switches to Bengali');
      await h.wait(1800);
      await h.page.evaluate(() => window.scrollBy({ top: 330, behavior: 'smooth' }));
      await h.wait(1600);
      await h.page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
      await h.wait(700);
      h.cap('Pandal names, crowd times, routes: all in বাংলা');
      await h.tap('.task[data-q="famous"]', 1800);
      await h.tap('#explorePanel .item[data-place="sovabazar_rajbari"]', 1200);
      await h.scrollTo('.sheet .hours', { offset: 160, ms: 1000 });
      await h.wait(2600);
    },
  },
  {
    id: 'whatsapp',
    async run(h) {
      h.cap('Open any pandal');
      await h.wait(600);
      await h.type('#homeSearch', 'suruchi');
      await h.wait(500);
      await h.tap('#homeResults li[data-result="suruchi_sangha"]', 1500);
      h.cap('Tap “WhatsApp”');
      const href = await h.page.getAttribute('#waShare', 'href');
      await h.tap('#waShare', 900);
      const text = decodeURIComponent(href.replace(/^https:\/\/wa\.me\/\?text=/, '')).replace(/https?:\/\/\S+/, '').trim();
      h.cap('The message is ready: just pick your family group');
      await h.overlay(`<div style="width:100%;max-width:340px;font-family:Roboto,'Noto Sans Bengali',sans-serif">
        <div style="color:#fff;opacity:.85;font-size:13px;margin:0 0 8px 6px">Message preview</div>
        <div style="background:#DCF8C6;color:#111;border-radius:14px 14px 4px 14px;padding:12px 14px;font-size:15px;line-height:1.4;box-shadow:0 6px 20px rgba(0,0,0,.35)">
          ${text.replace(/&/g, '&amp;').replace(/</g, '&lt;')}<div style="margin-top:8px;padding:8px 10px;background:rgba(0,0,0,.06);border-radius:8px;font-size:13px;color:#075E54">🔗 Opens ${'Suruchi Sangha'} in Pujo Parikrama</div></div></div>`, 3000);
      await h.page.evaluate(() => document.querySelector('.demo-overlay')?.remove());
      h.cap('They open it straight on that pandal: crowd, food, metro');
      await h.wait(2400);
    },
  },
];

/* ---------------- screenshots for the carousel and story ---------------- */
async function shots() {
  const dir = path.join(out, 'raw', 'shots'); mkdirSync(dir, { recursive: true });
  const snap = async (page, name) => { await page.waitForTimeout(500); await page.screenshot({ path: path.join(dir, name + '.png') }); console.log('  shot', name); };
  {
    const { ctx, page } = await newPhone();
    await snap(page, 'home');
    await page.click('.task[data-q="famous"]'); await page.waitForTimeout(600);
    await snap(page, 'famous-list');
    await page.click('#explorePanel .item[data-place="santosh_mitra"]'); await page.waitForTimeout(700);
    await page.evaluate(() => { const s = document.querySelector('#sheet'), h = document.querySelector('.sheet .hours'); s.scrollTop = h.getBoundingClientRect().top - s.getBoundingClientRect().top + s.scrollTop - 150; });
    await snap(page, 'quiet-hours');
    await page.keyboard.press('Escape'); await page.waitForTimeout(300);
    await page.click('.tab[data-view="home"]');
    await page.fill('#homeSearch', 'ekdalia'); await page.click('#homeResults li[data-result="ekdalia"]'); await page.waitForTimeout(700);
    await page.evaluate(() => { const s = document.querySelector('#sheet'), h = document.querySelectorAll('.sheet h3.sh')[1]; s.scrollTop = h.getBoundingClientRect().top - s.getBoundingClientRect().top + s.scrollTop - 40; });
    await snap(page, 'getting-there');
    await page.keyboard.press('Escape'); await page.waitForTimeout(300);
    // the wizard
    await page.click('.tab[data-view="plan"]');
    await page.click('#view-plan [data-pz="north"]'); await page.click('#view-plan [data-pr="central"]');
    await snap(page, 'wizard-areas');
    await page.click('#planNext'); await page.click('#planStartBtn'); await page.fill('#pickSearch', 'shyam'); await page.click('[data-pick="t:shyambazar"]');
    await page.selectOption('#planBudget', '360'); await page.waitForTimeout(300);
    await snap(page, 'wizard-start');
    await page.click('#planForm button[type="submit"]'); await page.waitForSelector('.timeline li[data-place]'); await page.waitForTimeout(800);
    await snap(page, 'route-result');
    await page.evaluate(() => { const t = document.querySelector('.timeline'); window.scrollTo(0, t.getBoundingClientRect().top + window.scrollY - 120); });
    await snap(page, 'route-timeline');
    // check in + live
    await page.click('.tab[data-view="home"]');
    await page.fill('#homeSearch', 'tridhara'); await page.click('#homeResults li[data-result="tridhara"]'); await page.waitForTimeout(500);
    await page.click('#visitBtn'); await page.waitForFunction(() => document.querySelector('#toast').classList.contains('show'), null, { timeout: 8000 });
    await page.waitForTimeout(300);
    await snap(page, 'checked-in');
    await page.keyboard.press('Escape'); await page.waitForTimeout(300);
    await page.click('.tab[data-view="explore"]'); if (await page.locator('#modeBtn[data-to="list"]').count()) await page.click('#modeBtn[data-to="list"]'); await page.selectOption('#sortSelect', 'live'); await page.waitForFunction(() => !document.querySelector('#toast').classList.contains('show'), null, { timeout: 15000 }).catch(() => {});
    await snap(page, 'live-list');
    await page.click('#modeBtn[data-to="map"]'); await page.waitForTimeout(900);
    await snap(page, 'map');
    // Bengali
    await page.click('.tab[data-view="home"]'); await page.click('#langBtn'); await page.waitForTimeout(500);
    await snap(page, 'home-bn');
    await page.click('#langBtn');
    // share row
    await page.fill('#homeSearch', 'suruchi'); await page.click('#homeResults li[data-result="suruchi_sangha"]'); await page.waitForTimeout(700);
    await snap(page, 'share-row');
    await ctx.close();
  }
  {
    const { ctx, page } = await newPhone({ kind: 'me' });
    await page.click('.tab[data-view="me"]'); await page.waitForTimeout(500);
    await snap(page, 'me');
    await page.evaluate(() => { const b = document.querySelector('.badges'); window.scrollTo(0, b.getBoundingClientRect().top + window.scrollY - 330); });
    await snap(page, 'me-badges');
    const dl = page.waitForEvent('download'); await page.click('#myCardBtn');
    await (await dl).saveAs(path.join(dir, 'pujo-card.png'));
    await ctx.close();
  }
}

try {
  mkdirSync(path.join(out, 'raw'), { recursive: true });
  if (doReels) for (const r of REELS) if (!only.length || only.includes(r.id)) { console.log('recording', r.id); await recordReel(r); }
  if (doShots && (!only.length || only.includes('shots'))) { console.log('screenshots'); await shots(); }
} finally {
  await browser.close();
  server.kill();
  fake.server.close();
}
