// Mobile end-to-end test (iPhone 13 viewport).
//   node tests/e2e/smoke.mjs [outDir]
// Serves app/ on a free port and drives every tab plus the full community loop: verified
// check-in, a too-far check-in, "I ate here", an offline-queued check-in, photo upload,
// like, and the feed. It runs against an in-memory fake Supabase, or a real one when
// SUPABASE_URL and SUPABASE_ANON_KEY are set (CI does this with `supabase start`).
import { chromium, devices } from 'playwright';
import { spawn } from 'node:child_process';
import { readFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { startFakeSupabase } from './fake-supabase.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const out = path.resolve(process.argv[2] || path.join(root, 'screenshots'));
mkdirSync(out, { recursive: true });
const guidePath = path.join(root, 'app/data/guide.json');
const G = JSON.parse(readFileSync(guidePath, 'utf8'));
const P = Object.fromEntries([...G.pandals, ...G.food].map((p) => [p.id, p]));

let backend, fake = null;
if (process.env.SUPABASE_URL) backend = { url: process.env.SUPABASE_URL, anonKey: process.env.SUPABASE_ANON_KEY };
else { fake = await startFakeSupabase({ guidePath }); backend = fake; }
const statFor = async (id) => {
  const r = await fetch(`${backend.url}/rest/v1/place_stats?place_id=eq.${id}&select=*`, { headers: { apikey: backend.anonKey } });
  const rows = await r.json(); return (Array.isArray(rows) ? rows.find((x) => x.place_id === id) : null) || { visits: 0, today: 0, photos: 0 };
};

const port = 8200 + Math.floor(Math.random() * 600);
const server = spawn('python3', ['-m', 'http.server', '-d', path.join(root, 'app'), String(port)], { stdio: 'ignore' });
const base = `http://127.0.0.1:${port}/`;
for (let i = 0; i < 50; i++) { try { await fetch(base); break; } catch { await new Promise((r) => setTimeout(r, 100)); } }

const at = (id) => ({ latitude: P[id].lat, longitude: P[id].lng, accuracy: 10 });
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined });
const ctx = await browser.newContext({ ...devices['iPhone 13'], geolocation: at('tridhara'), permissions: ['geolocation'] });
await ctx.addInitScript((cfg) => { window.PP_CONFIG = { community: cfg }; }, { url: backend.url, anonKey: backend.anonKey });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
page.on('console', (m) => { if (m.type() === 'error' && !/tile|cartocdn|ERR_|403|504|Failed to fetch|net::/.test(m.text())) errors.push('console: ' + m.text()); });

const shot = async (n) => { await page.waitForTimeout(250); await page.screenshot({ path: `${out}/${n}.png` }); };
const must = (cond, msg) => { if (!cond) throw new Error(msg); };
const count = (sel) => page.locator(sel).count();
// Wait for a toast matching `re` (badge toasts can arrive in between).
const waitToast = async (re, what) => {
  try { await page.waitForFunction((src) => { const el = document.querySelector('#toast'); return el.classList.contains('show') && new RegExp(src, 'i').test(el.textContent); }, re.source, { timeout: 8000 }); }
  catch { throw new Error(`${what}: expected toast ${re}, saw "${await page.locator('#toast').innerText()}"`); }
};
const closeSheet = async () => { await page.keyboard.press('Escape'); await page.waitForTimeout(250); };
// A real 64x48 PNG, generated in the page to avoid shipping a binary fixture.
const makePng = () => page.evaluate(async () => {
  const c = document.createElement('canvas'); c.width = 64; c.height = 48; const x = c.getContext('2d');
  x.fillStyle = '#C2410C'; x.fillRect(0, 0, 64, 48); x.fillStyle = '#FBBF24'; x.beginPath(); x.arc(32, 24, 14, 0, 7); x.fill();
  const b = await new Promise((r) => c.toBlob(r, 'image/png')); return Array.from(new Uint8Array(await b.arrayBuffer()));
});

try {
  await page.goto(base);
  await page.waitForSelector('.hero');
  must(await count('.tasks .task') === 6, 'task buttons missing on home');
  must(await count('[data-hr]') === G.regions.length, 'area buttons missing on home');
  await shot('01-home');
  // Home is a launcher: an area opens the map filtered to it; "Must-see" opens the famous list.
  await page.click('[data-hr="south"]');
  await page.waitForSelector('#view-explore.active[data-mode="list"] #explorePanel .item[data-place]');
  must(await page.locator('#areaSelect').inputValue() === 'r:south', 'home area button should filter the map to South');
  await page.click('.tab[data-view="home"]');
  await page.click('.task[data-q="famous"]');
  await page.waitForSelector('#view-explore.active #explorePanel .item[data-place]');
  await page.click('.tab[data-view="home"]');
  must(await count('#view-home .how li') === 3, '"How it works" should sit in the first fold');
  must(await page.locator('#radioFab').isVisible(), 'sticky radio button should show from the start');

  // Pujo Radio: stations of official uploads (YouTube itself may be unreachable here, so only the UI is checked)
  must(await count('.radio-card .stations [data-station]') === 5, 'five radio stations expected');
  await page.click('.stations [data-station="dhak"]');
  await page.waitForSelector('.stations [data-station="dhak"][aria-checked="true"]');
  must(await count('.radio-card .tracks [data-track]') >= 3, 'dhak station should list its tracks');
  must(/Pujar Dhak/.test(await page.locator('.radio-card .tracks').innerText()), 'dhak tracks missing');
  await page.locator('.radio-card').scrollIntoViewIfNeeded();
  await shot('01b-radio');

  // All of Kolkata in 6 days: a day opens its timed route
  must(await count('#view-home .dayplan [data-dayplan]') === 6, 'six day plans expected');
  await page.click('#view-home [data-dayplan="2"]');
  await page.waitForSelector('#view-plan.active .stepper [data-step="3"][aria-current="step"]');
  must(await count('.timeline li[data-place]') >= 4, 'Saptami day plan should have a route');
  await shot('01c-dayplan');
  await page.click('#planNew');
  await page.click('.tab[data-view="home"]');

  // Search (English and Bengali)
  await page.fill('#homeSearch', 'tridh');
  await page.waitForSelector('#homeResults li[data-result="tridhara"]');
  await page.fill('#homeSearch', 'ত্রিধারা');
  await page.waitForSelector('#homeResults li[data-result="tridhara"]');
  await page.fill('#homeSearch', 'chorbag');
  await page.waitForSelector('#homeResults li[data-result="chorbagan"]');
  await shot('02-search');
  await page.fill('#homeSearch', 'tridh');
  await page.waitForSelector('#homeResults li[data-result="tridhara"]');

  // Verified check-in at Tridhara: counts publicly
  const before = (await statFor('tridhara')).visits;
  await page.click('#homeResults li[data-result="tridhara"]');
  await page.waitForSelector('.sheet.open #visitBtn');
  await page.click('#visitBtn');
  await waitToast(/checked in|Visitor/, 'check-in');
  await page.waitForTimeout(400);
  must((await statFor('tridhara')).visits === before + 1, 'community visit count did not increase');
  must(await page.locator('#visitBtn').isDisabled(), 'check-in button should show done');
  await shot('03-checked-in');
  await closeSheet();

  // Too far: Bagbazar from Lake Market is refused publicly, but can be kept privately
  await page.click('.tab[data-view="explore"]');
  // The Map tab: one filter row, and a pill that flips between a full-screen map and the list
  await page.selectOption('#areaSelect', 'all');
  await page.click('#modeBtn[data-to="map"]');
  await page.waitForSelector('#view-explore[data-mode="map"] #map.leaflet-container');
  must(await page.locator('#explorePanel').isHidden(), 'list should hide in map mode');
  must(/107|\d+ pandals/.test(await page.locator('#modeBtn').innerText()), 'map pill should show the count');
  await shot('03b-map-mode');
  await page.click('#modeBtn[data-to="list"]');
  await page.waitForSelector('#view-explore[data-mode="list"] #explorePanel .item');
  await page.selectOption('#areaSelect', 'a:north');
  must(await count('#explorePanel .item') === G.zones.find((z) => z.id === 'north').pandal_ids.length, 'area filter count');
  await page.click('#explorePanel .item[data-place="bagbazar"]');
  await page.click('#visitBtn');
  await page.waitForSelector('#privBtn');
  must(/away/.test(await page.locator('#verifyBox').innerText()), 'too-far notice missing');
  await shot('04-too-far');
  await page.click('#privBtn');
  await page.waitForTimeout(300);
  must((await statFor('bagbazar')).visits === 0, 'a too-far visit must not count publicly');
  await closeSheet();

  // "I ate here" at a food spot, standing at it
  const foodId = G.food.find((f) => f.zone === 'south_lakemarket').id;
  await ctx.setGeolocation(at(foodId));
  await page.click('#exploreBar [data-seg="food"]');
  await page.selectOption('#areaSelect', 'all');
  await page.click(`#explorePanel .item[data-place="${foodId}"]`);
  await page.click('#visitBtn');
  await waitToast(/#1|Logged/, 'ate here');
  await page.waitForTimeout(300);
  must((await statFor(foodId)).visits >= 1, 'ate-here not counted');
  await closeSheet();
  await shot('05-food');

  // Offline check-in queues, then syncs when the network returns
  await ctx.setGeolocation(at('66_pally'));
  await page.click('#exploreBar [data-seg="pandals"]');
  await ctx.setOffline(true);
  await page.click('#explorePanel .item[data-place="66_pally"]');
  await page.click('#visitBtn');
  await waitToast(/sync|Checked in/, 'offline check-in');
  await closeSheet();
  await ctx.setOffline(false);
  await page.evaluate(() => window.dispatchEvent(new Event('online')));
  await page.waitForTimeout(1500);
  must((await statFor('66_pally')).visits === 1, 'queued check-in did not sync after reconnecting');

  // Parking segment and the car spot
  await page.click('#exploreBar [data-seg="parking"]');
  must(await count('#explorePanel .item'), 'no parking listed');
  if (fake) await page.waitForSelector('#explorePanel .notice.traffic a[href*="puja2026.pdf"]');  // live KTP notice from traffic_notices
  await shot('06-parking');

  // Moments: upload a photo at Tridhara (on-site), then like it
  await ctx.setGeolocation(at('tridhara'));
  await page.click('.tab[data-view="moments"]');
  await page.waitForSelector('#fabAdd:not([hidden])');
  await page.click('#fabAdd');
  await page.waitForSelector('#upGallery');
  const png = Buffer.from(await makePng());
  const [chooser] = await Promise.all([page.waitForEvent('filechooser'), page.click('#upGallery')]);
  await chooser.setFiles({ name: 'pandal.png', mimeType: 'image/png', buffer: png });
  await page.waitForSelector('#upPreview img');
  await page.waitForFunction(() => document.querySelector('#upPlace')?.value === 'tridhara', null, { timeout: 8000 })
    .catch(async () => { throw new Error(`nearest place should be preselected, got ${await page.locator('#upPlace').inputValue()}`); });
  await page.fill('#upCaption', 'Lights at Tridhara');
  await page.check('#upConsent');
  await shot('07-upload');
  await page.click('#upPost');
  await waitToast(/On site|Posted/, 'post');
  await page.waitForSelector('#view-moments .thumb');
  must((await statFor('tridhara')).photos >= 1, 'photo not counted');
  await shot('08-moments');
  await page.click('#view-moments .thumb >> nth=0');
  await page.waitForSelector('#mLike');
  await page.click('#mLike');
  await page.waitForFunction(() => document.querySelector('#mLike')?.getAttribute('aria-pressed') === 'true');
  must(/Lights at Tridhara/.test(await page.locator('.sheet').innerText()), 'caption missing in viewer');
  await shot('09-moment-view');
  await closeSheet();

  // Photos: a pandal gallery with credits, and dish photos at an eatery
  await page.click('.tab[data-view="home"]');
  await page.fill('#homeSearch', 'sreebhumi');
  await page.click('#homeResults li[data-result="sreebhumi"]');
  await page.waitForSelector('.sheet.open .gallery .gal');
  await page.click('.sheet.open .gallery .gal >> nth=0');
  await page.waitForSelector('#phBack');
  must(/Wikimedia Commons/.test(await page.locator('.sheet').innerText()), 'photo credit missing');
  await shot('10a-photo');
  await page.click('#phBack');
  await page.waitForSelector('.sheet.open #visitBtn');
  await closeSheet();
  await page.fill('#homeSearch', 'coffee house');
  await page.click('#homeResults li[data-result="coffee_house"]');
  await page.waitForSelector('.sheet.open .gallery.dishes .gal.dish');
  await shot('10b-food-photos');
  await closeSheet();

  // Curated trail with ride legs, then a custom route with a time budget, then the share link
  await page.click('.tab[data-view="plan"]');
  await page.click('#view-plan [data-trail="all_nighter"]');
  await page.waitForSelector('.timeline li.ride');
  must(/Line|Bus|auto|Cab/i.test(await page.locator('.timeline li.ride >> nth=0').innerText()), 'ride leg has no transport advice');
  must(await count('.timeline li.hop') >= 1, 'far-apart pandals should get an auto/bus/metro hop');
  must(/google\.com\/maps\/dir/.test(await page.locator('#planNextDir').getAttribute('href')), 'one Directions-to-next button expected');
  await shot('10-trail');
  // The wizard: 1 areas → 2 start point → 3 route
  await page.click('#planNew');
  await page.waitForSelector('.stepper [data-step="1"][aria-current="step"]');
  await page.click('#view-plan [data-pz="south_lakemarket"]');
  await shot('10c-wizard-areas');
  await page.click('#planNext');
  await page.waitForSelector('.stepper [data-step="2"][aria-current="step"]');
  await page.selectOption('#planBudget', '180');
  await page.click('#planStartBtn');
  await page.fill('#pickSearch', 'kalig');
  await page.click('[data-pick="t:kalighat"]');
  await page.waitForTimeout(300);
  must(/Kalighat/.test(await page.locator('#planStartBtn').innerText()), 'start picker did not set Kalighat');
  await shot('10d-wizard-start');
  await page.click('#planForm button[type="submit"]');
  await page.waitForTimeout(400);
  await page.waitForSelector('.stepper [data-step="3"][aria-current="step"]');
  const stops = await count('.timeline li[data-place]');
  must(stops >= 3, `custom 3 h Lake Market plan should fit 3+ pandals, got ${stops}`);
  const params = await page.evaluate(() => JSON.parse(localStorage.getItem('pp:activePlan')).params);
  const enc = Buffer.from(JSON.stringify(params)).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  const shared = await ctx.newPage();
  await shared.goto(base + '#plan=' + enc);
  await shared.waitForSelector('.timeline li[data-place]');
  must(await shared.locator('.timeline li[data-place]').count() === stops, 'shared plan produced a different route');
  await shared.close();

  // Me: walk tracking with GPS plus simulated accelerometer steps
  await page.click('.tab[data-view="me"]');
  await page.click('#walkBtn');
  for (let i = 1; i <= 6; i++) {
    await ctx.setGeolocation({ latitude: P.tridhara.lat - 0.000036 * i, longitude: P.tridhara.lng, accuracy: 10 });
    await page.waitForTimeout(1500);
  }
  must(parseFloat(await page.locator('#fitKm').innerText()) > 0.01, 'walk distance not tracked');
  const s0 = +(await page.locator('#fitSteps').innerText()).replace(/,/g, '');
  await page.evaluate(async () => {
    for (let i = 0; i < 50 * 6; i++) {
      const z = 9.81 + 2.5 * Math.sin(2 * Math.PI * 2 * (i / 50));
      window.dispatchEvent(new DeviceMotionEvent('devicemotion', { accelerationIncludingGravity: { x: 0.1, y: 0.2, z } }));
      await new Promise((r) => setTimeout(r, 20));
    }
  });
  await page.waitForTimeout(1200);
  const s1 = +(await page.locator('#fitSteps').innerText()).replace(/,/g, '');
  must(s1 - s0 >= 8, `motion sensor steps not counted (${s0} → ${s1})`);
  must(await page.locator('.chips [data-place="tridhara"]').count() === 1, 'visited list missing Tridhara');
  await shot('11-me');

  // Growth: a story-size card, a tracked deep link (?src=…#p=…), the WhatsApp share link, and the open count
  const dl = page.waitForEvent('download', { timeout: 8000 });
  await page.click('#myCardBtn');
  must(/my-pujo-2026\.png$/.test((await dl).suggestedFilename()), 'story card not produced');
  // A new phone scanning a QR poster: lands on the pandal, and the open is counted with its source.
  const ctx2 = await browser.newContext({ ...devices['iPhone 13'] });
  await ctx2.addInitScript((cfg) => { window.PP_CONFIG = { community: cfg }; }, { url: backend.url, anonKey: backend.anonKey });
  const p2 = await ctx2.newPage();
  p2.on('pageerror', (e) => errors.push('pageerror (qr): ' + e.message));
  await p2.goto(base + '?src=qr_test#p=sreebhumi');
  await p2.waitForSelector('.sheet.open #waShare');
  must(!/src=/.test(p2.url()), 'tracking code not tidied from the URL: ' + p2.url());
  const wa = decodeURIComponent(await p2.getAttribute('#waShare', 'href'));
  must(wa.startsWith('https://wa.me/?text=') && wa.includes('?src=wa_place#p=sreebhumi'), 'WhatsApp link wrong: ' + wa);
  await p2.waitForTimeout(250); await p2.screenshot({ path: `${out}/11b-share-row.png` });
  if (fake) {
    await p2.waitForTimeout(1800);
    const st = await (await fetch(`${fake.url}/__state`)).json();
    must(st.opens.some((o) => o.src === 'qr_test' && o.first_src === 'qr_test'), 'open not counted with its source: ' + JSON.stringify(st.opens));
  }
  await ctx2.close();

  // Bengali, dark mode, offline reload
  await page.selectOption('#langSelect', 'bn');
  must((await page.locator('#tab-home span').innerText()) === 'হোম', 'tabs not translated');
  await page.click('.tab[data-view="home"]');
  await shot('12-home-bn');
  await page.selectOption('#langSelect', 'hi');
  must((await page.locator('#tab-home span').innerText()) === 'होम', 'tabs not translated to Hindi');
  await shot('12b-home-hi');
  await page.selectOption('#langSelect', 'en');
  await page.emulateMedia({ colorScheme: 'dark' });
  await shot('13-home-dark');
  await page.reload(); await page.waitForSelector('.hero');
  await ctx.setOffline(true);
  await page.reload();
  await page.waitForSelector('.hero', { timeout: 8000 });
  await ctx.setOffline(false);
  must(!(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)), 'horizontal overflow on mobile');
} catch (e) {
  errors.push(e.message);
  await page.screenshot({ path: `${out}/failure.png` }).catch(() => {});
} finally {
  await browser.close();
  server.kill();
  fake?.server.close();
}

if (errors.length) { console.error('SMOKE FAILED\n' + errors.join('\n')); process.exit(1); }
console.log(`smoke OK (${fake ? 'fake' : 'real'} backend) → screenshots in ${out}`);
