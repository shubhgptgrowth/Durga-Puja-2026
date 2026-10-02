// Mobile smoke test: node tests/e2e/smoke.mjs [baseUrl] [outDir]
// Serves nothing itself; run `python -m http.server -d app 8123` first.
import { chromium, devices } from 'playwright';

const base = process.argv[2] || 'http://localhost:8123/';
const out = process.argv[3] || 'screenshots';
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

const shot = (n) => page.screenshot({ path: `${out}/${n}.png` });
const expect = async (sel, what) => { if (!(await page.locator(sel).count())) throw new Error(`missing ${what} (${sel})`); };

await page.goto(base);
await page.waitForSelector('#pandalList .card');
await expect('.leaflet-marker-icon', 'map markers');
await shot('01-explore');

await page.click('#zoneChips [data-z="north"]');
await expect('.zbox', 'zone banner');
const n = await page.locator('#pandalList .card').count();
if (n !== 12) throw new Error(`expected 12 north pandals, got ${n}`);
await shot('02-explore-north');

await page.click('#pandalList .card >> nth=0');
await page.waitForSelector('.sheet.open');
await page.waitForTimeout(300);
await shot('03-pandal-sheet');
await page.click('#sheetClose');

await page.click('.tab[data-view="plan"]');
await page.waitForSelector('#itinList .card');
await shot('04-plan-curated');
await page.click('#itinList .card >> nth=2');
await page.waitForSelector('.timeline li[data-p]');
await page.waitForTimeout(400);
await shot('05-plan-itinerary');

await page.click('.seg-btn[data-seg="custom"]');
await page.click('#planZones [data-z="south_lakemarket"]');
await page.selectOption('#planBudget', '180');
await page.click('#planForm button[type="submit"]');
await page.waitForTimeout(500);
const stops = await page.locator('.timeline li[data-p]').count();
if (stops < 2) throw new Error('custom plan produced too few stops');
await page.evaluate(() => window.scrollTo(0, 0));
await shot('06-plan-custom');

await page.click('.tab[data-view="food"]');
await page.click('#foodFilters [data-f="sweets"]');
await expect('#foodList .card', 'food cards');
await shot('07-food');

await page.click('.tab[data-view="park"]');
await page.click('#parkZones [data-z="south_lakemarket"]');
await shot('08-park');

await page.click('.tab[data-view="fit"]');
await page.click('#walkBtn');
// Simulate a slow walk south from Tridhara: about 4 m every 1.6 s, which is ~9 km/h and under the vehicle cut-off.
for (let i = 1; i <= 10; i++) {
  await ctx.setGeolocation({ latitude: 22.5185 - 0.000036 * i, longitude: 88.3489, accuracy: 10 });
  await page.waitForTimeout(1600);
}
await page.waitForTimeout(600);
const checked = await page.locator('#fitPandals').innerText();
if (+checked < 1) throw new Error('GPS auto check-in did not fire');
const walked = parseFloat(await page.locator('#fitKm').innerText());
if (!(walked > 0.01)) throw new Error(`walk distance not tracked (${walked} km)`);
await shot('09-fit');

await page.emulateMedia({ colorScheme: 'dark' });
await page.click('.tab[data-view="explore"]');
await page.waitForTimeout(300);
await shot('10-explore-dark');

const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
if (overflow) errors.push('horizontal overflow on mobile');

await browser.close();
if (errors.length) { console.error(errors.join('\n')); process.exit(1); }
console.log(`smoke OK: ${stops} custom stops, ${checked} pandal(s) auto-checked-in`);
