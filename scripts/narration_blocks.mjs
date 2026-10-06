// What the Listen player reads on each guide page, for scripts/narrate.py. Uses the page's own guide.js
// (window.__ppgListenBlocks), so a recording always matches what the player highlights.
//   node scripts/narration_blocks.mjs <built site dir> <out.json>
import { chromium } from 'playwright';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';

const [root = 'app', outFile = 'narration-blocks.json'] = process.argv.slice(2);
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.webp': 'image/webp', '.woff2': 'font/woff2', '.svg': 'image/svg+xml', '.png': 'image/png' };
const srv = http.createServer((q, r) => {
  let f = path.join(root, decodeURIComponent(q.url.split('?')[0]));
  if (f.endsWith('/')) f += 'index.html';
  fs.readFile(f, (err, b) => { if (err) { r.writeHead(404); r.end(); } else { r.writeHead(200, { 'content-type': types[path.extname(f)] || 'application/octet-stream' }); r.end(b); } });
}).listen(8098);
const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).flatMap((e) => e.isDirectory() ? walk(path.join(d, e.name)) : e.name === 'index.html' ? [path.join(d, e.name)] : []);
const pages = ['durga-puja', 'navratri', 'festivals'].filter((d) => fs.existsSync(path.join(root, d))).flatMap((d) => walk(path.join(root, d)))
  .filter((f) => fs.readFileSync(f, 'utf8').includes('data-listen'))
  .map((f) => path.relative(root, path.dirname(f)).split(path.sep).join('/') + '/');
const b = await chromium.launch();
const p = await b.newPage();
await p.route(/^https?:\/\/(?!localhost)/, (r) => r.abort());   // no ads or fonts from elsewhere
const out = {};
for (const page of pages.sort()) {
  await p.goto(`http://localhost:8098/${page}`, { waitUntil: 'domcontentloaded' });
  await p.waitForFunction(() => window.__ppgListenBlocks);
  out[page] = await p.evaluate(() => window.__ppgListenBlocks());
}
await b.close(); srv.close();
fs.writeFileSync(outFile, JSON.stringify(out));
console.log(`${Object.keys(out).length} pages, ${Object.values(out).reduce((n, x) => n + x.blocks.length, 0)} blocks → ${outFile}`);
