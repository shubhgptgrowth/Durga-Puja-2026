// Validates the Web Stories (AMP) and takes phone screenshots of a few pages of each: CI only (needs cdn.ampproject.org).
//   node scripts/story_check.mjs <built site dir> [screenshot dir] [slug,slug…: only these get screenshots]
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';

const root = process.argv[2] || 'app', shots = process.argv[3], only = (process.argv[4] || '').split(',').filter(Boolean);
const dirs = fs.readdirSync(path.join(root, 'stories'), { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => d.name);
let bad = 0;
for (const d of dirs) {
  try { execFileSync('npx', ['-y', 'amphtml-validator', path.join(root, 'stories', d, 'index.html')], { stdio: 'pipe' }); console.log('PASS', d); }
  catch (e) { bad++; console.log('FAIL', d, '\n' + String(e.stdout || '') + String(e.stderr || '')); }
}
if (shots) {
  const types = { '.html': 'text/html', '.webp': 'image/webp', '.jpg': 'image/jpeg', '.png': 'image/png', '.woff2': 'font/woff2', '.svg': 'image/svg+xml', '.css': 'text/css', '.js': 'text/javascript' };
  const srv = http.createServer((q, r) => {
    let f = path.join(root, decodeURIComponent(q.url.split('?')[0]));
    if (f.endsWith('/')) f += 'index.html';
    fs.readFile(f, (err, b) => { if (err) { r.writeHead(404); r.end(); } else { r.writeHead(200, { 'content-type': types[path.extname(f)] || 'application/octet-stream' }); r.end(b); } });
  }).listen(8099);
  fs.mkdirSync(shots, { recursive: true });
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 390, height: 780 }, deviceScaleFactor: 1 });
  for (const d of dirs.filter((x) => !only.length || only.includes(x))) {
    await p.goto(`http://localhost:8099/stories/${d}/`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(2500);
    for (const id of ['cover', 'p1', 'p3', 'end']) {
      await p.goto(`http://localhost:8099/stories/${d}/#page=${id}`, { waitUntil: 'networkidle' });
      await p.waitForTimeout(1800);
      await p.screenshot({ path: path.join(shots, `${d}--${id}.png`) });
    }
  }
  await b.close(); srv.close();
}
console.log(`${dirs.length - bad}/${dirs.length} stories valid AMP`);
process.exit(bad ? 1 : 0);
