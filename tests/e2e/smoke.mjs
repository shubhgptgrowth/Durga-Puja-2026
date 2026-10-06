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
  must(await count('#view-home .how li') === 4, 'the how-to steps should be on Home');
  // Nothing plays until someone asks for music, so the sticky radio button stays away until then
  must(!(await page.locator('#radioFab').isVisible()), 'sticky radio button should be hidden while no music plays');
  // A newcomer sees what this is and one thing to do: the promise, "Plan my pujo" and search, right under the banner
  must(await count('#view-home .promise .promise-cta[data-q="myplan"]') === 1, 'Plan my pujo button missing');
  must(await count('#view-home .promise #homeSearch') === 1, 'search should sit right under the promise');

  // Pujo Radio: stations of official uploads (YouTube itself may be unreachable here, so only the UI is checked)
  must(await count('.radio-card .st-tiles [data-station]') === 5, 'five radio stations expected');
  must(await count('.hero.slides .slide') >= 3, 'banner slideshow expected');
  // Tapping the banner opens the pandal on the visible slide (the hidden slides used to swallow taps)
  const shown = await page.locator('#slidePlace').innerText();
  await page.click('.hero.slides .slide.on');
  await page.waitForSelector('.sheet.open h2.title');
  must((await page.locator('.sheet.open h2.title').innerText()).trim() === shown.trim(), `banner opened the wrong pandal (expected ${shown})`);
  await closeSheet();
  must(await count('.hero-credit') === 0, 'no photo credit on the banner');
  // Tap pads: a dhak stroke and the shankh
  await page.click('.radio-card [data-sfx="dhak"]');
  await page.click('.radio-card [data-sfx="shankh"]');
  await page.click('.st-tiles [data-station="dhak"]');
  await page.waitForSelector('.st-tiles [data-station="dhak"][aria-checked="true"]');
  await page.click('.radio-card .tracks-wrap summary');
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
  await page.waitForSelector('.cheer', { timeout: 3000 });          // petals + "জয় মা!"
  await shot('03a-cheer');
  await page.waitForTimeout(400);
  must((await statFor('tridhara')).visits === before + 1, 'community visit count did not increase');
  must(await page.locator('#visitBtn').isDisabled(), 'check-in button should show done');
  // First check-in unlocks "Prothom Darshan": the medallion pops up over the page, which stays open
  await page.waitForSelector('.badge-modal .medal', { timeout: 6000 });
  await shot('03b-badge');
  await page.click('#bdDone');
  must(await page.locator('.sheet.open #visitBtn').count() === 1, 'the pandal page should still be open under the badge');
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
  // Puja-day chips on the page: footfall follows the chosen day (Saptami by default before the pujo)
  await page.waitForSelector('.sheet.open .day-toggle [data-sday="saptami"][aria-checked="true"]');
  const estOf = async () => (await page.locator('.sheet.open .stat.est b').innerText()).trim();
  const sapt = await estOf();
  await page.click('.sheet.open [data-sday="panchami"]');
  await page.waitForSelector('.sheet.open [data-sday="panchami"][aria-checked="true"]');
  must((await estOf()) !== sapt, 'footfall estimate should change with the day');
  await page.click('.sheet.open [data-sday="saptami"]');
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
  // Rate it: only possible after "I ate here"; the average shows on the page and in the list
  await page.waitForSelector('.sheet.open #rateForm');
  await page.click('#rateForm [data-star="4"]');
  await page.click('#rateForm [data-rtag="tasty"]');
  await page.click('#rateForm [type="submit"]');
  await waitToast(/Thanks/, 'rating');
  await page.waitForSelector('.sheet.open .rating-sum b');
  must((await page.locator('.sheet.open .rating-sum b').innerText()) === '4', 'rating average not shown');
  must(/for 2/.test(await page.locator('.sheet.open .cost-chip').innerText()), 'cost for two missing on the eatery page');
  if (fake) must((await (await fetch(`${fake.url}/__state`)).json()).ratings === 1, 'rating not stored');
  await page.locator('.sheet.open .rating-sum').scrollIntoViewIfNeeded(); await shot('05b-rating');
  await closeSheet();
  must(/★ 4/.test(await page.locator(`#explorePanel .item[data-place="${foodId}"] .rating`).innerText()), 'rating not in the list');
  // Diet chips: Veg = pure veg, Egg = places with egg dishes
  await page.click('#exploreBar [data-f="egg"]');
  const eggN = await count('#explorePanel .item');
  must(eggN > 0 && eggN === await count('#explorePanel .item .egg-mark'), 'egg filter shows places without egg dishes');
  await page.click('#exploreBar [data-f="egg"]');
  await page.click('#exploreBar [data-f="veg"]');
  must(await count('#explorePanel .item') === G.food.filter((f) => f.veg === 'veg').length, 'veg filter count');
  await page.click('#exploreBar [data-f="veg"]');
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

  // Eatery: a menu photo (shown under Menu, not in Moments) and a restaurant's pujo offer (live after review)
  {
    const momentsBefore = await count('#view-moments .thumb');
    await page.click('.tab[data-view="home"]');
    await page.fill('#homeSearch', 'coffee house');
    await page.click('#homeResults li[data-result="coffee_house"]');
    await page.waitForSelector('.sheet.open [data-menu] .fine');
    await page.click('#addMenuBtn');
    await page.waitForSelector('#upGallery');
    const [ch] = await Promise.all([page.waitForEvent('filechooser'), page.click('#upGallery')]);
    await ch.setFiles({ name: 'menu.png', mimeType: 'image/png', buffer: Buffer.from(await makePng()) });
    await page.waitForSelector('#upPreview img');
    must(await page.locator('#upPlace').inputValue() === 'coffee_house', 'menu upload should be for this eatery');
    await page.click('#upPost');
    await waitToast(/Menu photo added/, 'menu photo');
    await page.waitForSelector('.sheet.open [data-menu] .thumb');
    await page.click('#postOfferBtn');
    await page.waitForSelector('#offerForm');
    await page.fill('#ofTitle', 'Free mishti doi with every thali');
    await page.fill('#ofName', 'Ratan');
    await page.fill('#ofPhone', '98300 12345');
    await page.check('#ofOwner');
    await shot('10c-offer-form');
    await page.click('#offerForm [type="submit"]');
    await waitToast(/call to confirm/, 'offer sent');
    if (fake) {
      const st = await (await fetch(`${fake.url}/__state`)).json();
      must(st.offers.length === 1 && st.offers[0].phone === '+919830012345' && st.offers[0].status === 'pending', 'offer not stored as pending');
      await fetch(`${fake.url}/__approveOffers`);
      await closeSheet();
      await page.reload(); await page.waitForSelector('.tab[data-view="explore"]');
      await page.click('.tab[data-view="explore"]');
      await page.click('#exploreBar [data-seg="food"]');
      await page.waitForSelector(`#explorePanel .item[data-place="coffee_house"] .offer-chip`, { timeout: 8000 });
      await page.click('#explorePanel .item[data-place="coffee_house"]');
      await page.waitForSelector('.sheet.open .offer-card');
      must(/Free mishti doi/.test(await page.locator('.sheet.open .offer-card').innerText()), 'approved offer not on the eatery page');
      must(!/98300/.test(await page.locator('.sheet.open').innerText()), 'owner phone must never show');
      await shot('10d-offer');
    }
    await closeSheet();
    await page.click('.tab[data-view="moments"]');
    await page.waitForTimeout(800);
    must(await count('#view-moments .thumb') === momentsBefore, 'menu photo leaked into Moments');
  }

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
  // Directions at the bottom: Google Maps links that together cover every stop, in order
  const legs = await page.locator('.route-dirs .dir-leg').evaluateAll((as) => as.map((a) => a.href));
  must(legs.length >= 1 && legs.every((u) => /google\.com\/maps\/dir/.test(u)), 'route directions missing');
  const stopsN = await count('.timeline li[data-place]');
  const covered = legs.reduce((n, u) => n + (decodeURIComponent(new URL(u).searchParams.get('waypoints') || '').split('|').filter(Boolean).length) + 1, 0);
  must(covered === stopsN, `directions cover ${covered} of ${stopsN} stops`);
  must(!(await count('#planNextDir')), 'the overview card should not carry a Directions button');
  await shot('10-trail');
  // How you're travelling changes every ride: walk → long walks, car → drive (+ parking)
  await page.click('.mode-row [data-mode="walk"]');
  const rides = (await page.locator('.timeline li.ride').allInnerTexts()).join(' | ');
  must(await count('.timeline li.hop.walk') >= 1 && !/🚇|🚌|🛺|🚕/.test(rides), 'walk mode still shows rides: ' + rides.slice(0, 300));
  await page.click('.mode-row [data-mode="car"]');
  must(/Drive/.test(await page.locator('.timeline li.ride >> nth=0').innerText()), 'car mode should drive');
  must((await page.locator('.route-dirs .dir-leg >> nth=0').getAttribute('href')).includes('travelmode=driving'), 'car directions should drive');
  await shot('10a-trail-car');
  await page.click('.mode-row [data-mode="any"]');
  // The wizard: 1 areas → 2 start point → 3 route
  await page.click('#planNew');
  await page.waitForSelector('.stepper [data-step="1"][aria-current="step"]');
  must(await count('#view-plan [data-pz]') === 0, 'step 1 should only show regions');
  await page.click('#view-plan [data-pr="south"]');
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
  // Badges open their own page; earned ones can be shared as a story card
  await page.click('[data-badge="first"]');
  await page.waitForSelector('.sheet.open .badge-pop #bdShare');
  const bdl = page.waitForEvent('download', { timeout: 8000 });
  await page.click('.sheet.open #bdShare');
  must(/pujo-badge-first\.png$/.test((await bdl).suggestedFilename()), 'badge card not produced');
  await closeSheet();
  await page.click('[data-badge="thirty"]');
  await page.waitForSelector('.sheet.open .badge-pop.locked');
  await closeSheet();
  await shot('11-me');
  // Steps copied from the phone's Health app win when higher than what the app tracked
  await page.click('.health-sync summary');
  await page.fill('#healthSteps', '23456');
  await page.click('#healthForm button[type="submit"]');
  await page.waitForFunction(() => document.querySelector('#fitSteps')?.textContent.replace(/\D/g, '') === '23456');

  // iPhone Shortcut sync: the Shortcut opens …#steps=N with Apple Health's total
  await page.goto(base + '?src=ios_shortcut#steps=12%2C345.0');
  await waitToast(/12,345 steps synced/, 'shortcut sync');
  must(/#me$/.test(page.url()), 'steps link should land on My Pujo with a tidy URL: ' + page.url());
  await page.waitForFunction(() => document.querySelector('#fitSteps')?.textContent.replace(/\D/g, '') === '12345');

  // Name (and, with consent, phone) for share cards
  await page.locator('.profile-box').scrollIntoViewIfNeeded(); await shot('11c-profile');
  // Phone: only 10 digits of an Indian mobile; pasted +91/0/spaces are tidied, letters dropped
  await page.fill('#cPhone', '+91 98300-12345');
  must(await page.inputValue('#cPhone') === '9830012345', 'pasted +91 number not tidied: ' + await page.inputValue('#cPhone'));
  await page.fill('#cPhone', '98300123456789abc');
  must(await page.inputValue('#cPhone') === '9830012345', 'more than 10 digits allowed');
  await page.fill('#cPhone', '5830012345');
  must(/6, 7, 8 or 9/.test(await page.locator('#phoneHint').innerText()), 'invalid number not flagged');
  await page.fill('#cName', 'Rina Sen');
  await page.fill('#cPhone', '98300 12345');
  // Walking redraws this page every second: unsaved text and open sections must survive it
  await page.click('.health-sync summary');
  await page.evaluate(() => document.activeElement?.blur());
  await page.evaluate(async () => {
    for (let i = 0; i < 50 * 3; i++) {
      window.dispatchEvent(new DeviceMotionEvent('devicemotion', { accelerationIncludingGravity: { x: 0.1, y: 0.2, z: 9.81 + 2.5 * Math.sin(2 * Math.PI * 2 * (i / 50)) } }));
      await new Promise((r) => setTimeout(r, 20));
    }
  });
  await page.waitForTimeout(1200);
  must(await page.inputValue('#cName') === 'Rina Sen' && await page.inputValue('#cPhone') === '9830012345', 'unsaved name/phone wiped by a redraw: ' + await page.inputValue('#cName') + '|' + await page.inputValue('#cPhone'));
  must(await page.locator('details.health-sync').evaluate((d) => d.open), 'opened section snapped shut on redraw');
  must(/shares it with the Pujo Parikrama team/.test(await page.locator('.share-note').innerText()), 'saving must say the number is shared');
  const [nb, pb] = await Promise.all(['#cName', '.phone-in'].map((sel) => page.locator(sel).boundingBox()));
  must(Math.abs(nb.x - pb.x) < 2 && Math.abs(nb.width - pb.width) < 2 && Math.abs(nb.height - pb.height) < 2, 'name and phone fields not aligned');
  await page.click('#contactForm button[type="submit"]');
  await waitToast(/Saved/, 'profile');
  must(await page.evaluate(async () => (await import('./growth.js')).myCard().title) === "Rina's Pujo 2026", 'name not on the story card');
  if (fake) {
    const st = await (await fetch(`${fake.url}/__state`)).json();
    must(st.profiles.some((x) => x.phone === '+919830012345' && x.name === 'Rina Sen' && x.lang === 'en' && x.device_id), 'profile not saved with consent and data points: ' + JSON.stringify(st.profiles));
    await page.click('.profile-box summary').catch(() => {});
    await page.click('#cRemove');
    await waitToast(/erased/, 'profile erased');
    must((await (await fetch(`${fake.url}/__state`)).json()).profiles.length === 0, '"Remove my number" must erase it');
    must(await page.inputValue('#cPhone').catch(() => '') === '', 'number still shown after removing');
  }

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
  // Place page layout: "I'm here" beside the name, photos in the first fold, Directions + one Share at the bottom
  must(await p2.locator('.sheet.open .title-row #visitBtn').count() === 1, "I'm here should sit beside the name");
  must(await p2.locator('.sheet.open .sheet-cta a').count() === 2 && /maps\/dir/.test(await p2.getAttribute('.sheet.open .sheet-cta a.primary', 'href')), 'bottom bar should hold Directions and Share');
  must(!(await p2.locator('.sheet.open .action-bar, .sheet.open #storyShare, .sheet.open #linkShare, .sheet.open .share-row').count()), 'old top Directions / extra share buttons still there');
  must(!(await p2.locator('.sheet.open .mini-list ~ .btn-row a[href*="travelmode=transit"]').count()), 'the separate bus & metro directions button should be gone');
  const galTop = await p2.locator('.sheet.open .gallery').first().evaluate((e) => e.getBoundingClientRect().top);
  must(galTop < 844, 'photos should be in the first fold, top at ' + galTop);
  await p2.waitForTimeout(250); await p2.screenshot({ path: `${out}/11b-share-row.png` });
  if (fake) {
    await p2.waitForTimeout(1800);
    const st = await (await fetch(`${fake.url}/__state`)).json();
    must(st.opens.some((o) => o.src === 'qr_test' && o.first_src === 'qr_test'), 'open not counted with its source: ' + JSON.stringify(st.opens));
  }
  await ctx2.close();

  // Analytics: anonymous events reach the backend; the live strip shows real counts once they are big enough
  if (fake) {
    await page.evaluate(async () => (await import('./analytics.js')).flush());
    const ev = (await (await fetch(`${fake.url}/__state`)).json()).events;
    for (const n of ['view', 'place_open', 'checkin', 'rate', 'filter', 'share']) must(ev.some((e) => e.name === n), `no ${n} event: ` + JSON.stringify(ev.slice(0, 5)));
    must(ev.some((e) => e.name === 'place_open' && e.kind === 'food'), 'eatery opens not tagged');
    must(ev.some((e) => e.name === 'view' && e.detail === 'me'), 'page views missing');
    must(!JSON.stringify(ev).includes('Rina'), 'events must not carry the name');
    await page.click('.tab[data-view="home"]');
    must(await page.locator('#liveStrip').isHidden(), 'small all-time counts must not be shown');
    await fetch(`${fake.url}/__crowd?live=1482&people=12345`);
    await page.reload(); await page.waitForSelector('.hero');
    await page.waitForSelector('#livePill:not([hidden])', { timeout: 8000 });
    const pill = await page.locator('#livePill').innerText();
    must(/1,48\d\s*online/.test(pill), 'header live count: ' + pill);
    const strip = await page.locator('#liveStrip').innerText();
    must(/12,300\+ have planned/.test(strip), 'live strip: ' + strip);
    await shot('01c-live');
    await fetch(`${fake.url}/__crowd?live=0&people=0`);
  }

  // My Pujo on another browser: the progress here is backed up under a Pujo code; a fresh browser opening its
  // link gets the same check-ins and steps back, and its own progress is merged in, not wiped.
  {
    await page.click('.tab[data-view="me"]');
    const code = await page.waitForFunction(() => JSON.parse(localStorage.getItem('pp:pujoCode') || 'null'), null, { timeout: 15000 }).then((h) => h.jsonValue());
    must(/^PUJO-[A-Z2-9]{4}-[A-Z2-9]{4}$/.test(code), 'pujo code: ' + code);
    await page.click('details.sync-box summary');
    must((await page.locator('#pujoCode').innerText()) === code, 'code shown on My Pujo');
    await page.locator('details.sync-box').scrollIntoViewIfNeeded(); await shot('11q-sync-card');
    const mine = await page.evaluate(() => Object.keys(JSON.parse(localStorage.getItem('pp:checkins') || '{}')));
    must(mine.length > 0, 'expected check-ins to back up');
    const ctx2 = await browser.newContext({ ...devices['iPhone 13'] });
    await ctx2.addInitScript((cfg) => { window.PP_CONFIG = { community: cfg }; }, { url: backend.url, anonKey: backend.anonKey });
    await ctx2.addInitScript(() => { if (!localStorage.getItem('pp:history')) localStorage.setItem('pp:history', JSON.stringify({ '2026-10-01': { m: 900, ms: 0, pandals: [], foods: [], steps: 1234 } })); });
    const p2 = await ctx2.newPage();
    p2.on('pageerror', (e) => errors.push('pageerror (2nd browser): ' + e.message));
    // This browser already has a day of its own before the link is opened
    await p2.goto(base + '#restore=' + code.toLowerCase().replace('pujo-', ''));
    await p2.waitForFunction((c) => JSON.parse(localStorage.getItem('pp:pujoCode') || 'null') === c, code, { timeout: 8000 });
    const got = await p2.evaluate(() => ({ checkins: Object.keys(JSON.parse(localStorage.getItem('pp:checkins') || '{}')), hist: JSON.parse(localStorage.getItem('pp:history') || '{}') }));
    must(mine.every((id) => got.checkins.includes(id)), 'restored check-ins: ' + got.checkins.join(','));
    must(got.hist['2026-10-01']?.steps === 1234, 'second browser lost its own steps in the merge: ' + JSON.stringify(got.hist));
    must(await p2.locator('#view-me.active').count() === 1 && !p2.url().includes('restore='), 'restore link should land on My Pujo: ' + p2.url());
    await p2.screenshot({ path: `${out}/11r-restored.png` });
    // A wrong code says so and changes nothing
    await p2.click('details.sync-box summary').catch(() => {});
    await p2.fill('#syCode', 'PUJO-ZZZZ-ZZZZ'); await p2.click('#syncForm button');
    await p2.waitForFunction(() => /No backup/.test(document.querySelector('#toast')?.textContent || ''), null, { timeout: 5000 });
    must(await p2.evaluate(() => JSON.parse(localStorage.getItem('pp:pujoCode'))) === code, 'a wrong code must not switch the backup');
    await ctx2.close();
  }

  // Google sign-in: the guest account is linked (same user, same backup); a second browser signing in with the
  // same Google account gets everything back automatically and keeps its own steps. (The fake backend plays
  // Google; a real local stack has no Google provider, so there the button must stay hidden.)
  if (!fake) {
    await page.click('.tab[data-view="me"]'); await page.waitForTimeout(800);
    must(!(await count('#gSignIn')), 'Continue with Google shown though the project has Google sign-in off');
  } else {
    await page.click('.tab[data-view="me"]');
    await page.waitForSelector('#gSignIn', { timeout: 8000 });
    const before = await page.evaluate(() => ({ uid: JSON.parse(localStorage.getItem('pp:sb.session')).user.id, code: JSON.parse(localStorage.getItem('pp:pujoCode')) }));
    await page.locator('.account-box').scrollIntoViewIfNeeded(); await shot('11s-google-card');
    await page.click('#gSignIn');
    await page.waitForSelector('.account-box.signed', { timeout: 10000 });
    must(/rina@gmail\.com/.test(await page.locator('.account-box.signed').innerText()), 'signed-in email not shown');
    must(!/access_token/.test(page.url()) && /#me$/.test(page.url()), 'tokens left in the URL: ' + page.url());
    const after = await page.evaluate(() => ({ uid: JSON.parse(localStorage.getItem('pp:sb.session')).user.id, code: JSON.parse(localStorage.getItem('pp:pujoCode')) }));
    must(after.uid === before.uid && after.code === before.code, 'linking should keep the same account and backup: ' + JSON.stringify({ before, after }));
    await waitToast(/Signed in/, 'google sign-in');
    await page.locator('.account-box').scrollIntoViewIfNeeded(); await shot('11t-google-signed');
    const mine = await page.evaluate(() => Object.keys(JSON.parse(localStorage.getItem('pp:checkins') || '{}')));

    const ctx3 = await browser.newContext({ ...devices['iPhone 13'] });
    await ctx3.addInitScript((cfg) => { window.PP_CONFIG = { community: cfg }; }, { url: backend.url, anonKey: backend.anonKey });
    await ctx3.addInitScript(() => { if (!localStorage.getItem('pp:history')) localStorage.setItem('pp:history', JSON.stringify({ '2026-10-02': { m: 500, ms: 0, pandals: [], foods: [], steps: 777 } })); });
    const p3 = await ctx3.newPage();
    p3.on('pageerror', (e) => errors.push('pageerror (google 2nd browser): ' + e.message));
    await p3.goto(base + '#me');
    await p3.waitForSelector('#gSignIn', { timeout: 8000 });
    await p3.click('#gSignIn');
    await p3.waitForSelector('.account-box.signed', { timeout: 10000 });
    await p3.waitForFunction((c) => JSON.parse(localStorage.getItem('pp:pujoCode') || 'null') === c, after.code, { timeout: 8000 });
    const got = await p3.evaluate(() => ({ checkins: Object.keys(JSON.parse(localStorage.getItem('pp:checkins') || '{}')), hist: JSON.parse(localStorage.getItem('pp:history') || '{}'),
      uid: JSON.parse(localStorage.getItem('pp:sb.session')).user.id }));
    must(got.uid === after.uid, 'second browser should sign in to the same account');
    must(mine.every((id) => got.checkins.includes(id)), 'check-ins not restored after Google sign-in: ' + got.checkins.join(','));
    must(got.hist['2026-10-02']?.steps === 777, 'second browser lost its own steps on sign-in');
    await ctx3.close();
  }

  // Privacy policy page, and "Delete all my data" erasing the server copy too (in a separate browser)
  {
    const ctx4 = await browser.newContext({ ...devices['iPhone 13'] });
    await ctx4.addInitScript((cfg) => { window.PP_CONFIG = { community: cfg }; }, { url: backend.url, anonKey: backend.anonKey });
    await ctx4.addInitScript(() => { if (!sessionStorage.getItem('seeded')) { sessionStorage.setItem('seeded', '1'); localStorage.setItem('pp:history', JSON.stringify({ '2026-10-03': { m: 400, ms: 0, pandals: [], foods: [], steps: 555 } })); } });
    const p4 = await ctx4.newPage();
    p4.on('pageerror', (e) => errors.push('pageerror (delete): ' + e.message));
    await p4.goto(base + 'privacy.html');
    must(/Privacy policy/.test(await p4.locator('h1').innerText()) && /Delete all my data/.test(await p4.locator('main').innerText()), 'privacy page');
    await p4.goto(base + '#me');
    const code = await p4.waitForFunction(() => JSON.parse(localStorage.getItem('pp:pujoCode') || 'null'), null, { timeout: 15000 }).then((h) => h.jsonValue());
    if (fake) must(code in (await (await fetch(`${fake.url}/__state`)).json()).progress, 'backup should exist before deleting');
    await p4.click('details.settings summary');
    p4.once('dialog', (d) => d.accept());
    await Promise.all([p4.waitForEvent('load', { timeout: 15000 }), p4.click('#resetBtn')]);
    await p4.waitForSelector('.tab');
    const left = await p4.evaluate(() => ({ code: localStorage.getItem('pp:pujoCode'), hist: localStorage.getItem('pp:history') }));
    must(!left.code && (!left.hist || !left.hist.includes('555')), 'local data should be gone: ' + JSON.stringify(left));
    if (fake) must(!(code in (await (await fetch(`${fake.url}/__state`)).json()).progress), 'server backup should be deleted');
    await ctx4.close();
  }

  // Back button: closes an open page, then returns to the previous tab, never leaving the site
  await page.click('.tab[data-view="home"]');
  await page.click('.tab[data-view="explore"]');
  await page.click('#exploreBar [data-seg="pandals"]');
  await page.click('#explorePanel .item[data-place]');
  await page.waitForSelector('.sheet.open');
  await page.goBack(); await page.waitForTimeout(300);
  must(!(await page.locator('.sheet.open').count()) && await page.locator('#view-explore.active').count() === 1, 'Back should close the page and stay on Explore');
  await page.goBack(); await page.waitForTimeout(300);
  must(await page.locator('#view-home.active').count() === 1 && page.url().startsWith(base), 'Back should return to Home: ' + page.url());

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
