// Checks that the self-hosted vector base map renders (run after scripts/build_tiles.sh).
//   node tests/e2e/map_tiles.mjs [screenshotDir]
// Serves app/ with HTTP range support (like GitHub Pages and Cloudflare), opens Explore on a phone
// viewport, and confirms the map switched to vector tiles and painted real map pixels in English and Bengali.
import { chromium, devices } from 'playwright';
import http from 'node:http';
import { createReadStream, statSync, existsSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../app');
const out = path.resolve(process.argv[2] || 'screenshots');
mkdirSync(out, { recursive: true });
if (!existsSync(path.join(root, 'tiles/kolkata.json'))) { console.error('no app/tiles/kolkata.json; run scripts/build_tiles.sh first'); process.exit(1); }

const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml', '.webmanifest': 'application/manifest+json' };
const server = http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x');
  let f = path.join(root, decodeURIComponent(u.pathname));
  if (!f.startsWith(root)) { res.writeHead(403).end(); return; }
  if (existsSync(f) && statSync(f).isDirectory()) f = path.join(f, 'index.html');
  if (!existsSync(f)) { res.writeHead(404).end(); return; }
  const size = statSync(f).size, type = TYPES[path.extname(f)] || 'application/octet-stream';
  const m = /bytes=(\d+)-(\d*)/.exec(req.headers.range || '');
  if (m) {
    const start = +m[1], end = m[2] ? Math.min(+m[2], size - 1) : size - 1;
    res.writeHead(206, { 'Content-Type': type, 'Content-Range': `bytes ${start}-${end}/${size}`, 'Content-Length': end - start + 1, 'Accept-Ranges': 'bytes' });
    createReadStream(f, { start, end }).pipe(res);
  } else {
    res.writeHead(200, { 'Content-Type': type, 'Content-Length': size, 'Accept-Ranges': 'bytes' });
    createReadStream(f).pipe(res);
  }
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}/`;

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined });
const ctx = await browser.newContext({ ...devices['iPhone 13'] });
await ctx.addInitScript(() => { window.PP_CONFIG = { community: { url: '' } }; });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));

// Fraction of sampled pixels in the map's canvases that differ from the background (i.e. roads, water, labels).
const painted = () => page.evaluate(() => {
  const cvs = [...document.querySelectorAll('#map canvas')];
  let diff = 0, n = 0;
  for (const c of cvs) {
    if (!c.width) continue;
    const x = c.getContext('2d'), d = x.getImageData(0, 0, c.width, c.height).data, bg = d.slice(0, 3);
    for (let i = 0; i < d.length; i += 4 * 97) { n++; if (Math.abs(d[i] - bg[0]) + Math.abs(d[i + 1] - bg[1]) + Math.abs(d[i + 2] - bg[2]) > 30) diff++; }
  }
  return { canvases: cvs.length, ratio: n ? diff / n : 0 };
});

let ok = true;
try {
  await page.goto(base + '#explore');
  await page.waitForSelector('#map.leaflet-container');
  const engine = await page.waitForFunction(async () => (await import('./ui.js')).mapEngine() === 'vector', null, { timeout: 15000 }).then(() => 'vector').catch(() => 'raster');
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(3500);
  const en = await painted();
  await page.screenshot({ path: `${out}/map-vector-en.png` });
  await page.click('#langBtn'); await page.waitForTimeout(3500);
  const bn = await painted();
  await page.screenshot({ path: `${out}/map-vector-bn.png` });
  console.log(`engine=${engine} canvases=${en.canvases} painted(en)=${en.ratio.toFixed(2)} painted(bn)=${bn.ratio.toFixed(2)}`);
  ok = engine === 'vector' && en.canvases > 0 && en.ratio > 0.05 && bn.ratio > 0.05 && !errors.length;
} catch (e) { errors.push(e.message); ok = false; }
await browser.close(); server.close();
if (errors.length) console.error('errors:\n' + errors.join('\n'));
console.log(ok ? 'vector map OK' : 'VECTOR MAP CHECK FAILED');
process.exit(ok ? 0 : 1);
