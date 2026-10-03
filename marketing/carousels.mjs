// Renders the Instagram carousels built by `python -m marketing.carousels --out <dir>`.
//   node marketing/carousels.mjs <dir>            → <dir>/<nn-slug>/slide-01.jpg … (1080×1350 JPEG)
//   ONLY=food node marketing/carousels.mjs <dir>  → just the carousels whose id matches
// Text-first slides in the same visual language as marketing/render.mjs (maroon → rust gradient, cream
// accents, the diya, concentric rings). Each slide shrinks its type a step at a time until it fits, and
// the run reports any slide that had to shrink a lot or still overflows.
import { chromium } from 'playwright';
import { readFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';

const dir = path.resolve(process.argv[2] || 'content/carousels');
const spec = JSON.parse(readFileSync(path.join(dir, 'carousels.json'), 'utf8'));
const [W, H] = spec.size;
const HANDLE = spec.handle;
const esc = (s = '') => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const FONTS = `<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@500;700&family=Poppins:wght@500;700;800&display=swap" rel="stylesheet">`;
const LINE = { blue: '#2563EB', green: '#16A34A', purple: '#7C3AED', orange: '#EA580C', suburban: '#475569' };

const CSS = `
*{box-sizing:border-box;margin:0;padding:0}
html{font-size:10px;overflow:hidden;width:100%;height:100%}
body{width:${W}px;height:${H}px;position:relative;overflow:hidden;font-family:Poppins,"DejaVu Sans","Hind Siliguri","Noto Sans Bengali",FreeSans,system-ui,sans-serif;color:var(--fg)}
.bn{font-family:"Hind Siliguri","Noto Sans Bengali",FreeSans,sans-serif;font-weight:700}
.red{--fg:#fff;--acc:#FDE68A;--muted:rgba(255,255,255,.86);--card:rgba(255,255,255,.12);--bub:#FDE68A;--bubfg:#7F1D1D;--ring:253,230,138}
.dark{--fg:#fff;--acc:#FDE68A;--muted:rgba(255,255,255,.84);--card:rgba(255,255,255,.10);--bub:#FDE68A;--bubfg:#7F1D1D;--ring:253,230,138}
.cream{--fg:#4C0519;--acc:#B91C1C;--muted:rgba(76,5,25,.82);--card:rgba(159,18,57,.09);--bub:#9F1239;--bubfg:#FDE68A;--ring:159,18,57}
.bg{position:absolute;inset:0}
.red .bg{background:linear-gradient(160deg,#9F1239 0%,#B91C1C 55%,#7C2D12 100%)}
.dark .bg{background:linear-gradient(160deg,#4C0519 0%,#7F1D1D 55%,#431407 100%)}
.cream .bg{background:linear-gradient(160deg,#FFFBEB 0%,#FEF3C7 55%,#FDE68A 100%)}
.rings{position:absolute;right:-260px;top:-260px;width:900px;height:900px;border-radius:50%;
  box-shadow:0 0 0 6px rgba(var(--ring),.16),0 0 0 110px transparent,0 0 0 116px rgba(var(--ring),.12),0 0 0 220px transparent,0 0 0 226px rgba(var(--ring),.08)}
.rings.b{right:auto;top:auto;left:-520px;bottom:-560px;opacity:.7}
.top{position:absolute;top:52px;left:72px;right:72px;display:flex;justify-content:space-between;align-items:center}
.brand{font-weight:700;color:var(--acc);font-size:34px;letter-spacing:.3px}
.count{font-size:28px;font-weight:700;border:3px solid var(--acc);color:var(--acc);border-radius:999px;padding:6px 22px}
.foot{position:absolute;bottom:50px;left:72px;right:72px;display:flex;justify-content:space-between;align-items:center;font-size:30px;font-weight:700}
.foot .h{color:var(--fg);opacity:.92}
.foot .sw{background:var(--acc);color:${'var(--bubfg)'};border-radius:999px;padding:12px 28px;font-size:30px}
.cream .foot .sw{color:#FDE68A}
.main{position:absolute;top:136px;bottom:136px;left:72px;right:72px;display:flex;flex-direction:column;overflow:hidden}
.kicker{font-size:3.6rem;font-weight:700;color:var(--acc);line-height:1.2}
.title{font-size:7.2rem;font-weight:800;line-height:1.05;margin-top:1rem;letter-spacing:-.5px}
.note{font-size:3.4rem;color:var(--muted);line-height:1.3;margin-top:auto;padding-top:2.4rem}
/* cover */
.s-cover .main{justify-content:center}
.tag{align-self:flex-start;background:var(--acc);color:#7F1D1D;font-weight:800;font-size:3.2rem;border-radius:999px;padding:1.2rem 3rem;margin-bottom:4rem}
.s-cover .title{font-size:11.4rem;line-height:1.0;margin-top:1.6rem}
.accent{font-size:6rem;font-weight:800;color:var(--acc);line-height:1.1;margin-top:2.6rem}
.sub{font-size:4.2rem;line-height:1.3;margin-top:3rem;color:var(--muted)}
.s-cover .bnl{font-size:4.4rem;line-height:1.35;margin-top:2.2rem}
/* list */
ol{list-style:none;display:flex;flex-direction:column;gap:2rem;margin-top:3.4rem}
li{display:flex;gap:2.6rem;align-items:center;background:var(--card);border-radius:2.8rem;padding:2.4rem 2.8rem}
li.ride{background:transparent;border:3px dashed rgba(var(--ring),.55);padding:1.6rem 2.8rem}
.bub{flex:0 0 auto;min-width:8.4rem;height:8.4rem;border-radius:4.2rem;background:var(--bub);color:var(--bubfg);font-weight:800;font-size:4rem;display:flex;align-items:center;justify-content:center;padding:0 1.6rem}
.bub.i{background:transparent;font-size:6.4rem;min-width:8.4rem;padding:0}
.bub.t{font-size:3.4rem;min-width:17rem;white-space:nowrap}
li .tx{flex:1;min-width:0}
li b{display:block;font-size:4.6rem;font-weight:800;line-height:1.12}
li .lbn{display:block;font-size:3.6rem;line-height:1.3;opacity:.92;margin-top:.2rem}
li small{display:block;font-size:3.5rem;color:var(--muted);line-height:1.25;margin-top:.6rem}
li.ride b{font-size:4rem}
.pill{flex:0 0 auto;font-size:3.2rem;font-weight:800;border-radius:999px;padding:1rem 2.2rem;background:var(--acc);color:#7F1D1D;white-space:nowrap}
.cream .pill{color:#FDE68A}
.pill.lo{background:#BBF7D0;color:#14532D}.pill.mid{background:#FDE68A;color:#7F1D1D}.pill.hi{background:#FECACA;color:#7F1D1D}
/* tip */
.s-tip .main{justify-content:center}
.ticon{font-size:17rem;line-height:1.1}
.s-tip .title{font-size:9rem;margin-top:2rem}
.s-tip .bnl{font-size:5rem;margin-top:1.4rem}
.body{font-size:5rem;line-height:1.32;margin-top:3.4rem}
.tfoot{align-self:flex-start;margin-top:4.4rem;background:var(--acc);color:#7F1D1D;font-weight:800;font-size:3.8rem;border-radius:999px;padding:1.4rem 3.4rem}
.cream .tfoot{color:#FDE68A}
/* tips (two blocks) */
.blocks{display:flex;flex-direction:column;gap:3.4rem;margin-top:4rem;flex:1;justify-content:center}
.block{background:var(--card);border-radius:3.6rem;padding:4rem 4.4rem}
.block .bi{font-size:10rem;line-height:1}
.block b{display:block;font-size:6.4rem;font-weight:800;line-height:1.1;margin-top:1.8rem}
.block p{font-size:4.4rem;line-height:1.32;margin-top:1.6rem;color:var(--muted)}
/* stats */
.stats{display:grid;grid-template-columns:1fr 1fr;gap:3rem;margin-top:4.4rem}
.stats.one{grid-template-columns:1fr}
.stat{background:var(--card);border-radius:3.6rem;padding:4.4rem 4rem}
.stat .v{font-size:9.6rem;font-weight:800;color:var(--acc);line-height:1.05;white-space:nowrap}
.stats.one .v{font-size:14rem}
.stat .l{font-size:4rem;line-height:1.3;margin-top:1.4rem}
/* bars */
.bars{display:flex;flex-direction:column;gap:2.6rem;margin-top:4.4rem}
.bar{display:grid;grid-template-columns:31rem 1fr 9rem;align-items:center;gap:2.2rem}
.bar .lb b{display:block;font-size:4.4rem;font-weight:800;line-height:1.1}
.bar .lb small{font-size:3.2rem;color:var(--muted)}
.track{height:5.4rem;border-radius:999px;background:rgba(255,255,255,.12);overflow:hidden}
.fill{height:100%;border-radius:999px;background:linear-gradient(90deg,#FDE68A,#FB923C)}
.fill.max{background:linear-gradient(90deg,#FB923C,#F43F5E)}
.bar .n{font-size:4.6rem;font-weight:800;color:var(--acc);text-align:right}
/* grid */
.grid{display:grid;grid-template-columns:1fr 1fr;gap:2.4rem;margin-top:4rem}
.cell{background:var(--card);border-radius:3rem;padding:3rem 3.2rem}
.cell .d{font-size:3.6rem;font-weight:700;color:var(--acc)}
.cell b{display:block;font-size:6rem;font-weight:800;line-height:1.1;margin-top:.6rem}
.cell .lbn{display:block;font-size:4.2rem;margin-top:.4rem}
.cell.hi{background:#9F1239;color:#fff}.cell.hi .d{color:#FDE68A}
.cell.end{background:transparent;border:3px dashed rgba(var(--ring),.5);display:flex;flex-direction:column;justify-content:center}
/* stations */
.st{background:var(--card);border-radius:3rem;padding:3rem 3.4rem}
.st .hd{display:flex;align-items:center;gap:2rem}
.chip{font-size:2.8rem;font-weight:800;color:#fff;border-radius:999px;padding:.8rem 2rem;white-space:nowrap}
.st .hd b{font-size:5.4rem;font-weight:800;line-height:1.1}
.st ul{list-style:none;margin-top:1.6rem}
.st ul li{display:block;background:none;padding:0;border-radius:0;font-size:4rem;line-height:1.4;color:var(--muted)}
.st ul li:before{content:"🪔 ";font-size:3.2rem}
.stations{display:flex;flex-direction:column;gap:2.6rem;margin-top:3.6rem}
/* words */
.words{display:flex;flex-direction:column;gap:2.8rem;margin-top:3.6rem}
.word{background:var(--card);border-radius:3rem;padding:3rem 3.6rem}
.word .w{font-size:6rem;font-weight:800;color:var(--acc);line-height:1.1}
.word .w .bn{font-size:4.6rem;color:var(--fg);margin-left:1.6rem;font-weight:700}
.word p{font-size:4rem;line-height:1.32;margin-top:1.2rem}
/* cta */
.s-cta .main{align-items:center;justify-content:center;text-align:center}
.s-cta .diya{font-size:20rem;line-height:1.1}
.s-cta .big{font-size:12rem;font-weight:800;line-height:1.05;margin-top:2rem}
.s-cta .mid{font-size:5.6rem;font-weight:700;margin-top:3rem;line-height:1.25}
.s-cta .btn{display:inline-block;background:var(--acc);color:#7F1D1D;font-weight:800;border-radius:999px;padding:2.8rem 6rem;font-size:5.2rem;margin-top:4.6rem}
.s-cta .hdl{font-size:6.4rem;font-weight:800;color:var(--acc);margin-top:4.4rem}
.s-cta .bnl{font-size:4.4rem;margin-top:2.4rem;opacity:.92}
`;

const bnl = (s, cls = 'bnl') => (s ? `<div class="bn ${cls}">${esc(s)}</div>` : '');
const head = (s) => `${s.kicker ? `<div class="kicker">${esc(s.kicker)}</div>` : ''}${s.title ? `<div class="title">${esc(s.title)}</div>` : ''}`;

function bubble(it, i, s) {
  if (it.badge) return `<div class="bub t">${esc(it.badge)}</div>`;
  if (it.icon) return `<div class="bub i">${esc(it.icon)}</div>`;
  if (s.start || it.n) return `<div class="bub">${it.n || s.start + i}</div>`;
  return '';
}

const T = {
  cover: (s) => `<div class="tag">${esc(s.tag)}</div><div class="kicker">${esc(s.kicker)}</div><div class="title">${esc(s.title)}</div>
    ${s.accent ? `<div class="accent">${esc(s.accent)}</div>` : ''}${s.sub ? `<div class="sub">${esc(s.sub)}</div>` : ''}${bnl(s.bn)}`,
  list: (s) => `${head(s)}<ol>${s.items.map((it, i) => `<li class="${it.ride ? 'ride' : ''}">${bubble(it, i, s)}<div class="tx"><b>${esc(it.name)}</b>
      ${it.bn ? `<span class="bn lbn">${esc(it.bn)}</span>` : ''}${it.meta ? `<small>${esc(it.meta)}</small>` : ''}${it.meta2 ? `<small>${esc(it.meta2)}</small>` : ''}</div>
      ${it.pill ? `<span class="pill ${it.level || ''}">${esc(it.pill)}</span>` : ''}</li>`).join('')}</ol>${s.note ? `<div class="note">${esc(s.note)}</div>` : ''}`,
  tip: (s) => `<div class="ticon">${esc(s.icon)}</div><div class="kicker" style="margin-top:2rem">${esc(s.kicker)}</div><div class="title">${esc(s.title)}</div>${bnl(s.bn)}
    <div class="body">${esc(s.body)}</div>${s.foot ? `<div class="tfoot">${esc(s.foot)}</div>` : ''}`,
  tips: (s) => `${head(s)}<div class="blocks">${s.items.map((it) => `<div class="block"><div class="bi">${esc(it.icon)}</div><b>${esc(it.title)}</b><p>${esc(it.body)}</p></div>`).join('')}</div>`,
  stats: (s) => `${head(s)}<div class="stats ${s.stats.length < 3 ? 'one' : ''}">${s.stats.map((x) => `<div class="stat"><div class="v">${esc(x.v)}</div><div class="l">${esc(x.l)}</div></div>`).join('')}</div>${s.note ? `<div class="note">${esc(s.note)}</div>` : ''}`,
  bars: (s) => {
    const max = Math.max(...s.bars.map((b) => b.v));
    return `${head(s)}<div class="bars">${s.bars.map((b) => `<div class="bar"><div class="lb"><b>${esc(b.label)}</b><small>${esc(b.date)} · <span class="bn">${esc(b.bn)}</span></small></div>
      <div class="track"><div class="fill ${b.v === max ? 'max' : ''}" style="width:${Math.round((100 * b.v) / max)}%"></div></div><div class="n">${b.v}</div></div>`).join('')}</div>${s.note ? `<div class="note">${esc(s.note)}</div>` : ''}`;
  },
  grid: (s) => `${head(s)}<div class="grid">${s.cells.map((c) => `<div class="cell ${c.hi ? 'hi' : ''}"><div class="d">${esc(c.top)}</div><b>${esc(c.big)}</b><span class="bn lbn">${esc(c.bn)}</span></div>`).join('')}
    <div class="cell end"><b style="font-size:5rem">🪔 Shubho Sharodiya</b><span class="bn lbn">শুভ শারদীয়া</span></div></div>`,
  stations: (s) => `${head(s)}<div class="stations">${s.items.map((it) => `<div class="st"><div class="hd"><span class="chip" style="background:${LINE[it.line] || '#334155'}">${esc(it.chip)}</span><b>${esc(it.name)}</b></div>
      <ul>${it.rows.map((r) => `<li>${esc(r)}</li>`).join('')}</ul></div>`).join('')}</div>`,
  words: (s) => `${head(s)}<div class="words">${s.items.map((it) => `<div class="word"><div class="w">${esc(it.name)}<span class="bn">${esc(it.bn)}</span></div><p>${esc(it.meta)}</p></div>`).join('')}</div>`,
  cta: (s) => `<div class="diya">🪔</div><div class="big">Save this 📌</div><div class="mid">Plan your pujo free:<br>quiet hours, routes, food, metro</div>
    <div class="btn">Link in bio →</div><div class="hdl">${esc(HANDLE)}</div>${bnl(s.bn)}`,
};

function slideHtml(s) {
  const last = s.page === s.pages;
  return `<!doctype html><html><head><meta charset="utf-8">${FONTS}<style>${CSS}</style></head>
  <body class="${s.theme || 'red'} s-${s.t}"><div class="bg"></div><div class="rings"></div><div class="rings b"></div>
  <div class="top"><div class="brand">🪔 Pujo Parikrama 2026</div><div class="count">${s.page} / ${s.pages}</div></div>
  <div class="main">${T[s.t](s)}</div>
  <div class="foot"><span class="h">${esc(HANDLE)}</span>${last ? '<span class="sw">Share 🔁</span>' : `<span class="sw">${s.page === 1 ? 'Swipe →' : 'Next →'}</span>`}</div>
  </body></html>`;
}

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined });
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
const only = process.env.ONLY ? new RegExp(process.env.ONLY) : null;
const issues = [];
let n = 0;
try {
  for (const c of spec.carousels) {
    if (only && !only.test(c.id)) continue;
    const out = path.join(dir, c.id);
    mkdirSync(out, { recursive: true });
    for (const s of c.slides) {
      await page.setContent(slideHtml(s), { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForLoadState('load', { timeout: 4000 }).catch(() => {});
      await Promise.race([page.evaluate(() => document.fonts.ready), new Promise((r) => setTimeout(r, 3000))]).catch(() => {});
      // Shrink the root size (all slide type is in rem) until the content fits its box.
      const fit = await page.evaluate((start) => {
        const m = document.querySelector('.main'), root = document.documentElement;
        const over = () => m.scrollHeight > m.clientHeight + 1 || m.scrollWidth > m.clientWidth + 1
          || [...m.querySelectorAll('li, .stat, .cell, .block, .word, .st')].some((e) => e.scrollWidth > e.clientWidth + 1);
        let px = start; root.style.fontSize = px + 'px';
        while (over() && px > 6.5) { px -= 0.25; root.style.fontSize = px + 'px'; }
        return { px, over: over() };
      }, ['list', 'stations', 'words', 'stats'].includes(s.t) ? 12 : s.t === 'tip' ? 11.5 : 10);
      await page.evaluate(() => { window.scrollTo(0, 0); document.querySelectorAll('*').forEach((e) => { e.scrollTop = 0; }); });
      if (fit.over || fit.px < 8.5) issues.push(`${c.id} slide ${s.page}: ${fit.over ? 'OVERFLOWS' : 'shrunk'} to ${Math.round(fit.px * 10)}%`);
      await page.screenshot({ path: path.join(out, `slide-${String(s.page).padStart(2, '0')}.jpg`), type: 'jpeg', quality: 90 });
      n++;
    }
  }
} finally {
  await browser.close();
}
console.log(`rendered ${n} slides → ${dir}`);
if (issues.length) console.log('check these slides:\n  ' + issues.join('\n  '));
