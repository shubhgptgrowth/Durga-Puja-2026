// Mobile end-to-end smoke test (iPhone 13 viewport).
//   node tests/e2e/smoke.mjs [outDir]
// Serves app/ on a free port, drives every tab, and fails on JS errors or broken flows.
// Set CHROME_PATH to use a specific Chromium build.
import { chromium, devices } from 'playwright';
import { spawn } from 'node:child_process';
import { readFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const out = path.resolve(process.argv[2] || path.join(root, 'screenshots'));
mkdirSync(out, { recursive: true });
const G = JSON.parse(readFileSync(path.join(root, 'app/data/guide.json'), 'utf8'));

const port = 8200 + Math.floor(Math.random() * 600);
const server = spawn('python3', ['-m', 'http.server', '-d', path.join(root, 'app'), String(port)], { stdio: 'ignore' });
const base = `http://127.0.0.1:${port}/`;
for (let i = 0; i < 50; i++) { try { await fetch(base); break; } catch { await new Promise((r) => setTimeout(r, 100)); } }

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined });
const ctx = await browser.newContext({
  ...devices['iPhone 13'],
  geolocation: { latitude: 22.5185, longitude: 88.3489 }, // Tridhara Sammilani
  permissions: ['geolocation'],
});
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
page.on('console', (m) => { if (m.type() === 'error' && !/tile|cartocdn|ERR_|403|504/.test(m.text())) errors.push('console: ' + m.text()); });

const shot = async (n) => { await page.waitForTimeout(250); await page.screenshot({ path: `${out}/${n}.png` }); };
const must = (cond, msg) => { if (!cond) throw new Error(msg); };
const count = (sel) => page.locator(sel).count();

try {
  await page.goto(base);
  await page.waitForSelector('#pandalList .card');
  must(await count('.leaflet-marker-icon'), 'map markers missing');
  must(await count('#pandalList .card') === G.pandals.length, 'pandal list incomplete');
  await shot('01-explore');

  // Zone filter
  await page.click('#zoneChips [data-z="north"]');
  const north = G.zones.find((z) => z.id === 'north').pandal_ids.length;
  must(await count('#pandalList .card') === north, `expected ${north} north pandals`);
  must(await count('.zbox'), 'zone banner missing');
  await shot('02-explore-north');

  // Keyboard: focus the first card and press Enter to open its sheet
  await page.focus('#pandalList .card >> nth=0');
  await page.keyboard.press('Enter');
  await page.waitForSelector('.sheet.open');
  await shot('03-pandal-sheet');
  await page.keyboard.press('Escape');
  must(!(await page.locator('.sheet.open').count()), 'Escape did not close the sheet');

  // Curated itinerary
  await page.click('.tab[data-view="plan"]');
  await page.waitForSelector('#itinList .card');
  await shot('04-plan-curated');
  await page.click('#itinList .card >> nth=2');
  await page.waitForSelector('.timeline li[data-p]');
  await shot('05-plan-itinerary');

  // Custom plan with a time budget
  await page.click('.seg-btn[data-seg="custom"]');
  await page.click('#planZones [data-z="south_lakemarket"]');
  await page.selectOption('#planBudget', '180');
  await page.click('#planForm button[type="submit"]');
  await page.waitForTimeout(400);
  const stops = await count('.timeline li[data-p]');
  must(stops >= 4, `custom 3h Lake Market plan should fit 4+ pandals, got ${stops}`);
  await page.evaluate(() => window.scrollTo(0, 0));
  await shot('06-plan-custom');

  // Share link round-trip: open the shared URL in a fresh page and expect the same stops
  const shareUrl = await page.evaluate(() => {
    const p = JSON.parse(localStorage.getItem('pp:activePlan'));
    return p.params;
  });
  must(shareUrl && shareUrl.z[0] === 'south_lakemarket', 'plan params not stored');
  const shared = await ctx.newPage();
  const enc = Buffer.from(JSON.stringify(shareUrl)).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  await shared.goto(base + '#plan=' + enc);
  await shared.waitForSelector('.timeline li[data-p]');
  must(await shared.locator('.timeline li[data-p]').count() === stops, 'shared plan produced a different route');
  await shared.close();

  // Food filters
  await page.click('.tab[data-view="food"]');
  await page.click('#foodFilters [data-f="sweets"]');
  must(await count('#foodList .card'), 'no sweets listed');
  await shot('07-food');

  // Parking
  await page.click('.tab[data-view="park"]');
  await page.click('#parkZones [data-z="south_lakemarket"]');
  must(await count('#parkList .card'), 'no parking listed');
  await shot('08-park');

  // Fit: GPS walk (slow enough to count as walking) plus simulated accelerometer steps
  await page.click('.tab[data-view="fit"]');
  await page.click('#walkBtn');
  for (let i = 1; i <= 8; i++) {
    await ctx.setGeolocation({ latitude: 22.5185 - 0.000036 * i, longitude: 88.3489, accuracy: 10 });
    await page.waitForTimeout(1500);
  }
  must(+(await page.locator('#fitPandals').innerText()) >= 1, 'GPS auto check-in did not fire');
  must(parseFloat(await page.locator('#fitKm').innerText()) > 0.01, 'walk distance not tracked');
  const before = +(await page.locator('#fitSteps').innerText()).replace(/,/g, '');
  await page.evaluate(async () => {
    for (let i = 0; i < 50 * 6; i++) { // 6 s of a 2 Hz walking cadence
      const z = 9.81 + 2.5 * Math.sin(2 * Math.PI * 2 * (i / 50));
      window.dispatchEvent(new DeviceMotionEvent('devicemotion', { accelerationIncludingGravity: { x: 0.1, y: 0.2, z } }));
      await new Promise((r) => setTimeout(r, 20));
    }
  });
  await page.waitForTimeout(1100);
  const after = +(await page.locator('#fitSteps').innerText()).replace(/,/g, '');
  must(after - before >= 8, `motion sensor steps not counted (${before} → ${after})`);
  must(/motion/i.test(await page.locator('#fitSource').innerText()), 'step source should say motion sensor');
  await shot('09-fit');

  // Bengali
  await page.click('#langBtn');
  must((await page.locator('.tab[data-view="fit"] span').innerText()) === 'ফিট', 'tab labels not translated');
  await page.click('.tab[data-view="explore"]');
  must(/[ঀ-৿]/.test(await page.locator('#pandalList .card h3 >> nth=0').innerText()), 'pandal names not in Bengali');
  await shot('10-explore-bn');
  await page.click('#langBtn');

  // Dark mode
  await page.emulateMedia({ colorScheme: 'dark' });
  await shot('11-explore-dark');

  // Offline: the service worker should serve the shell and data
  await page.reload(); await page.waitForSelector('#pandalList .card');
  await ctx.setOffline(true);
  await page.reload();
  await page.waitForSelector('#pandalList .card', { timeout: 8000 });
  await ctx.setOffline(false);

  must(!(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)), 'horizontal overflow on mobile');
} catch (e) {
  errors.push(e.message);
  await page.screenshot({ path: `${out}/failure.png` }).catch(() => {});
} finally {
  await browser.close();
  server.kill();
}

if (errors.length) { console.error('SMOKE FAILED\n' + errors.join('\n')); process.exit(1); }
console.log(`smoke OK → screenshots in ${out}`);
