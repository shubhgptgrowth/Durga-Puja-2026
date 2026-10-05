// Renders the Instagram carousels built by `python -m marketing.carousels --out <dir> [--photos]`.
//   node marketing/carousels.mjs <dir>            → <dir>/<nn-slug>/slide-01.jpg … (1080×1350 JPEG)
//   ONLY=food node marketing/carousels.mjs <dir>  → just the carousels whose id matches
// Photo-led, editorial look: every slide is a full-bleed real photograph (slide.photo, from marketing/photos.py)
// under a soft shadow, with magazine type on top — no drawn backgrounds, boxes or emoji art. List rows show the
// place's own photo as a thumbnail. Each slide prints its photo credit. Type shrinks a step at a time until it fits,
// and the run reports any slide that had to shrink a lot or still overflows.
// A post may set "size": [1080, 1920] (stories); slides without a photo fall back to a deep maroon-black frame.
import { chromium } from 'playwright';
import { readFileSync, mkdirSync, existsSync } from 'node:fs';
import path from 'node:path';

const dir = path.resolve(process.argv[2] || 'content/carousels');
const spec = JSON.parse(readFileSync(path.join(dir, spec_name()), 'utf8'));
const HANDLE = spec.handle || '@pujoparikrama.guide';
const esc = (s = '') => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
// Emoji read as clip-art on a photo; the words carry the meaning.
const plain = (s = '') => String(s).replace(/[\u{1F000}-\u{1FFFF}☀-➿️‍\u{1FA70}-\u{1FAFF}]/gu, '').replace(/^\s*👉\s*/, '').replace(/\s{2,}/g, ' ').trim();
const t = (s) => esc(plain(s));

function spec_name() { return process.env.SPEC || 'carousels.json'; }

const FONTS = `<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Galada&family=Hind+Siliguri:wght@500;600;700&family=Inter:wght@500;600;700;800&display=swap" rel="stylesheet">`;
const LINE = { blue: '#3B82F6', green: '#22C55E', purple: '#A855F7', orange: '#F97316', suburban: '#94A3B8' };

const photoCache = new Map();
function dataUri(rel) {
  if (!rel) return '';
  if (/^https?:/.test(rel)) return rel;
  if (!photoCache.has(rel)) {
    const f = path.join(dir, rel);
    photoCache.set(rel, existsSync(f) ? `data:image/jpeg;base64,${readFileSync(f).toString('base64')}` : '');
  }
  return photoCache.get(rel);
}

const CSS = (W, H) => `
*{box-sizing:border-box;margin:0;padding:0}
html{font-size:10px;overflow:hidden;width:100%;height:100%}
body{width:${W}px;height:${H}px;position:relative;overflow:hidden;background:#1a0d0a;color:#fff;
  font-family:Inter,"Hind Siliguri","Noto Sans Bengali","DejaVu Sans",system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.bn{font-family:"Hind Siliguri","Noto Sans Bengali",sans-serif;font-weight:600}
.ph{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:50% var(--py,40%);filter:saturate(1.06) contrast(1.03)}
.sh{position:absolute;inset:0}
/* light shadow for hero slides, heavier under dense text, never a flat colour block */
.hero .sh{background:linear-gradient(180deg,rgba(0,0,0,.55) 0%,rgba(0,0,0,0) 16%,rgba(0,0,0,0) 40%,rgba(10,4,2,.72) 62%,rgba(10,4,2,.93) 100%)}
.dense .sh{background:linear-gradient(180deg,rgba(0,0,0,.42) 0%,rgba(0,0,0,0) 12%,rgba(10,4,2,.18) 20%,rgba(10,4,2,.74) 34%,rgba(10,4,2,.86) 48%,rgba(10,4,2,.9) 100%)}
.nophoto .sh{background:radial-gradient(120% 80% at 70% 0%,#5b1414 0%,#1a0d0a 60%)}
.top{position:absolute;top:44px;left:64px;right:64px;display:flex;justify-content:space-between;align-items:center;text-shadow:0 2px 10px rgba(0,0,0,.6)}
.mark{font-family:Galada,"Hind Siliguri",cursive;font-size:40px;line-height:1;color:#fff}
.mark small{font-family:Inter,sans-serif;font-size:22px;font-weight:600;opacity:.85;margin-left:14px;letter-spacing:.2px}
.count{font-size:22px;font-weight:700;letter-spacing:2px;opacity:.9}
.foot{position:absolute;bottom:34px;left:64px;right:64px;display:flex;justify-content:space-between;align-items:flex-end;gap:24px;font-size:21px}
.cred{opacity:.62;font-weight:500;line-height:1.3;max-width:70%;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.sw{font-weight:700;font-size:24px;letter-spacing:.5px;white-space:nowrap}
.main{position:absolute;left:64px;right:64px;bottom:96px;top:130px;display:flex;flex-direction:column;justify-content:flex-end;overflow:hidden;text-shadow:0 2px 14px rgba(0,0,0,.45)}
.dense .main{justify-content:flex-start;top:var(--mt,330px)}
.kicker{font-size:2.6rem;font-weight:700;letter-spacing:.32rem;text-transform:uppercase;color:#FFC857;display:flex;align-items:center;gap:1.6rem}
.kicker:before{content:"";width:5rem;height:.35rem;background:#FFC857;flex:0 0 auto}
.title{font-family:"DM Serif Display",Georgia,serif;font-weight:400;font-size:8.4rem;line-height:1.02;margin-top:1.4rem;letter-spacing:-.05rem}
.bnl{font-size:4.4rem;line-height:1.35;margin-top:1.2rem;color:#fff}
.note{font-size:2.9rem;line-height:1.35;opacity:.8;margin-top:auto;padding-top:2.4rem}
/* cover */
.s-cover .title{font-size:12.4rem;line-height:.98}
.tag{position:absolute;top:110px;left:64px;font-size:2.4rem;font-weight:800;letter-spacing:.2rem;border:2px solid rgba(255,255,255,.85);border-radius:999px;padding:.9rem 2.2rem;text-shadow:none;background:rgba(0,0,0,.18)}
.accent{font-family:"DM Serif Display",serif;font-style:italic;font-size:5.6rem;color:#FFC857;line-height:1.1;margin-top:1.6rem}
.sub{font-size:3.5rem;line-height:1.35;margin-top:2rem;opacity:.92;max-width:92%}
.s-cover .bnl{font-size:4.6rem;margin-top:1.8rem}
/* list rows: photo thumbnail or a serif number, hairline dividers, no boxes */
ol{list-style:none;display:flex;flex-direction:column;margin-top:2.6rem}
li{display:flex;gap:2.6rem;align-items:center;padding:2.1rem 0;border-top:1px solid rgba(255,255,255,.22)}
li:last-child{border-bottom:1px solid rgba(255,255,255,.22)}
.th{flex:0 0 auto;width:13rem;height:13rem;border-radius:1.4rem;object-fit:cover;box-shadow:0 6px 20px rgba(0,0,0,.45)}
.num{flex:0 0 auto;min-width:7rem;font-family:"DM Serif Display",serif;font-size:7rem;line-height:1;color:#FFC857;text-align:left}
.num.t{font-family:Inter,sans-serif;font-weight:800;font-size:3.2rem;min-width:13rem;letter-spacing:.1rem}
li.ride{padding:1.4rem 0;opacity:.85}
li.ride b{font-size:3.6rem;font-weight:600}
li .tx{flex:1;min-width:0}
li b{display:block;font-size:4.4rem;font-weight:800;line-height:1.12;letter-spacing:-.05rem}
li .lbn{display:block;font-size:3.4rem;line-height:1.3;opacity:.9;margin-top:.2rem}
li small{display:block;font-size:3rem;opacity:.78;line-height:1.3;margin-top:.5rem;font-weight:500}
.pill{flex:0 0 auto;font-size:2.6rem;font-weight:800;border-radius:999px;padding:.9rem 2rem;white-space:nowrap;border:2px solid #FFC857;color:#FFC857;text-shadow:none}
.pill.lo{border-color:#86EFAC;color:#86EFAC}.pill.mid{border-color:#FFC857;color:#FFC857}.pill.hi{border-color:#FCA5A5;color:#FCA5A5}
/* tip */
.s-tip .title{font-size:9.6rem}
.body{font-size:4.2rem;line-height:1.38;margin-top:2.6rem;opacity:.96}
.tfoot{align-self:flex-start;margin-top:3.4rem;font-weight:800;font-size:3.2rem;border:2px solid #FFC857;color:#FFC857;border-radius:999px;padding:1.2rem 3rem;text-shadow:none}
/* tips (two blocks) */
.blocks{display:flex;flex-direction:column;gap:0;margin-top:3rem}
.block{padding:3.4rem 0;border-top:1px solid rgba(255,255,255,.25)}
.block b{display:block;font-family:"DM Serif Display",serif;font-weight:400;font-size:6.8rem;line-height:1.05}
.block p{font-size:3.8rem;line-height:1.38;margin-top:1.4rem;opacity:.9}
/* stats */
.stats{display:grid;grid-template-columns:1fr 1fr;gap:0 4rem;margin-top:3rem}
.stats.one{grid-template-columns:1fr}
.stat{padding:3.4rem 0;border-top:1px solid rgba(255,255,255,.25)}
.stat .v{font-family:"DM Serif Display",serif;font-size:10.4rem;color:#FFC857;line-height:1;white-space:nowrap}
.stats.one .v{font-size:15rem}
.stat .l{font-size:3.4rem;line-height:1.3;margin-top:1.2rem;opacity:.92}
/* bars */
.bars{display:flex;flex-direction:column;gap:2.4rem;margin-top:3.4rem}
.bar{display:grid;grid-template-columns:30rem 1fr 8rem;align-items:center;gap:2.2rem}
.bar .lb b{display:block;font-size:4rem;font-weight:800;line-height:1.1}
.bar .lb small{font-size:2.8rem;opacity:.75}
.track{height:1.6rem;border-radius:999px;background:rgba(255,255,255,.18);overflow:hidden}
.fill{height:100%;border-radius:999px;background:#FFC857}
.fill.max{background:#FF5A5F}
.bar .n{font-family:"DM Serif Display",serif;font-size:5.4rem;text-align:right}
/* grid */
.grid{display:grid;grid-template-columns:1fr 1fr;gap:0 4rem;margin-top:2.6rem}
.cell{padding:2.6rem 0;border-top:1px solid rgba(255,255,255,.25)}
.cell .d{font-size:2.8rem;font-weight:700;letter-spacing:.2rem;text-transform:uppercase;color:#FFC857}
.cell b{display:block;font-family:"DM Serif Display",serif;font-weight:400;font-size:6.4rem;line-height:1.05;margin-top:.6rem}
.cell .lbn{display:block;font-size:3.6rem;margin-top:.2rem;opacity:.9}
.cell.hi b{color:#FFC857}
.cell.end{display:flex;flex-direction:column;justify-content:center}
/* stations */
.stations{display:flex;flex-direction:column;margin-top:2.6rem}
.st{padding:2.6rem 0;border-top:1px solid rgba(255,255,255,.25)}
.st .hd{display:flex;align-items:center;gap:2rem}
.chip{font-size:2.4rem;font-weight:800;border-radius:999px;padding:.6rem 1.8rem;white-space:nowrap;border:2px solid currentColor;text-shadow:none}
.st .hd b{font-size:5rem;font-weight:800;line-height:1.1}
.st ul{list-style:none;margin-top:1.2rem}
.st ul li{display:block;padding:0;border:0;font-size:3.6rem;line-height:1.42;opacity:.9}
.st ul li:before{content:"→ ";color:#FFC857}
/* words */
.words{display:flex;flex-direction:column;margin-top:2.6rem}
.word{padding:2.8rem 0;border-top:1px solid rgba(255,255,255,.25)}
.word .w{font-family:"DM Serif Display",serif;font-size:6.6rem;color:#FFC857;line-height:1.05}
.word .w .bn{font-size:4.6rem;color:#fff;margin-left:1.8rem}
.word p{font-size:3.6rem;line-height:1.36;margin-top:1rem;opacity:.92}
/* cta */
.s-cta .main{align-items:flex-start}
.s-cta .big{font-family:"DM Serif Display",serif;font-size:13rem;line-height:.98}
.s-cta .mid{font-size:4.4rem;font-weight:600;margin-top:2.4rem;line-height:1.3;opacity:.95}
.s-cta .btn{display:inline-block;background:#fff;color:#1a0d0a;font-weight:800;border-radius:999px;padding:2.2rem 5rem;font-size:4.2rem;margin-top:4rem;text-shadow:none}
.s-cta .hdl{font-size:4.4rem;font-weight:800;margin-top:3rem;color:#FFC857}
.s-cta .bnl{font-size:4.2rem;margin-top:2rem}
/* Bengali titles set in Galada */
.title.bnt,.big.bnt{font-family:Galada,"Hind Siliguri",cursive;letter-spacing:0;line-height:1.15}
.s-cover .title.bnt{font-size:13rem}
.two{position:absolute;inset:0;display:grid;grid-template-columns:1fr 1fr;gap:6px;background:#000}
.two div{position:relative;overflow:hidden}
.two img{width:100%;height:100%;object-fit:cover}
.two span{position:absolute;top:150px;left:0;right:0;text-align:center;font-family:Galada,"Hind Siliguri",cursive;font-size:96px;text-shadow:0 3px 18px rgba(0,0,0,.8);z-index:2}
.s-split .title{font-size:10rem;text-align:center}.s-split .sub{text-align:center;max-width:none}
.s-cols .vs{margin-top:3.4rem}
.bnh{font-family:Galada,"Hind Siliguri",cursive!important;font-size:8rem!important;font-weight:400!important}
ul.cl{list-style:none;margin-top:1.6rem}
ul.cl li{display:block;padding:1.5rem 0;border-top:1px solid rgba(255,255,255,.25);font-size:4rem;line-height:1.25}
.bingo .bm{display:block;font-size:3.2rem;font-weight:700}.bingo .en{display:block;font-size:2.2rem;opacity:.8;margin-top:.5rem;font-weight:600}
/* post-only types (Wave 1 posts and stories, marketing/posts.py) */
.s-word .title,.s-quote .title{font-size:13rem}
.s-word .bnl,.s-quote .bnl{font-family:Galada,"Hind Siliguri",cursive;font-size:16rem;line-height:1.1;margin:0}
.s-quote .bnl{font-size:9rem}
.s-prompt .title{font-size:10rem}
.big-q{font-family:"DM Serif Display",serif;font-size:7.4rem;line-height:1.1;margin-top:2rem}
.vs{display:grid;grid-template-columns:1fr 1fr;gap:4rem;margin-top:3rem}
.vs div b{display:block;font-family:"DM Serif Display",serif;font-weight:400;font-size:6.4rem;line-height:1.05;color:#FFC857}
.vs div p{font-size:3.6rem;line-height:1.36;margin-top:1.2rem;opacity:.92}
.bingo{display:grid;grid-template-columns:repeat(3,1fr);gap:1.4rem;margin-top:3rem}
.bingo div{aspect-ratio:1/1;border:1.5px solid rgba(255,255,255,.55);border-radius:1.4rem;display:flex;align-items:center;justify-content:center;text-align:center;padding:1.2rem;font-size:3rem;font-weight:700;line-height:1.2;background:rgba(0,0,0,.28)}
`;

const bnl = (s, cls = 'bnl') => (s ? `<div class="bn ${cls}">${esc(s)}</div>` : '');
const BN = /[\u0980-\u09FF]/;
const ttl = (x, cls = 'title') => `<div class="${cls}${BN.test(x) ? ' bnt' : ''}">${t(x)}</div>`;
const head = (s) => `${s.kicker ? `<div class="kicker">${t(s.kicker)}</div>` : ''}${s.title ? ttl(s.title) : ''}`;

function lead(it, i, s) {
  if (it.thumb) return `<img class="th" src="${dataUri(it.thumb)}">`;
  if (it.badge) return `<div class="num t">${t(it.badge)}</div>`;
  if (s.start || it.n) return `<div class="num">${it.n || s.start + i}</div>`;
  return `<div class="num">${i + 1}</div>`;
}

const T = {
  cover: (s) => `<div class="kicker">${t(s.kicker)}</div>${ttl(s.title)}
    ${s.accent ? `<div class="accent">${t(s.accent)}</div>` : ''}${bnl(s.bn)}${s.sub ? `<div class="sub">${t(s.sub)}</div>` : ''}`,
  list: (s) => `${head(s)}<ol>${s.items.map((it, i) => `<li class="${it.ride ? 'ride' : ''}">${it.ride ? `<div class="num t">${t(it.badge)}</div>` : lead(it, i, s)}<div class="tx"><b>${t(it.name)}</b>
      ${it.bn ? `<span class="bn lbn">${esc(it.bn)}</span>` : ''}${it.meta ? `<small>${t(it.meta)}</small>` : ''}${it.meta2 ? `<small>${t(it.meta2)}</small>` : ''}</div>
      ${it.pill ? `<span class="pill ${it.level || ''}">${t(it.pill)}</span>` : ''}</li>`).join('')}</ol>${s.note ? `<div class="note">${t(s.note)}</div>` : ''}`,
  tip: (s) => `${head(s)}${bnl(s.bn)}<div class="body">${t(s.body)}</div>${s.foot ? `<div class="tfoot">${t(s.foot)}</div>` : ''}`,
  tips: (s) => `${head(s)}<div class="blocks">${s.items.map((it) => `<div class="block"><b>${t(it.title)}</b><p>${t(it.body)}</p></div>`).join('')}</div>`,
  stats: (s) => `${head(s)}<div class="stats ${s.stats.length < 3 ? 'one' : ''}">${s.stats.map((x) => `<div class="stat"><div class="v">${t(x.v)}</div><div class="l">${t(x.l)}</div></div>`).join('')}</div>${s.note ? `<div class="note">${t(s.note)}</div>` : ''}`,
  bars: (s) => {
    const max = Math.max(...s.bars.map((b) => b.v));
    return `${head(s)}<div class="bars">${s.bars.map((b) => `<div class="bar"><div class="lb"><b>${t(b.label)}</b><small>${t(b.date)} · <span class="bn">${esc(b.bn)}</span></small></div>
      <div class="track"><div class="fill ${b.v === max ? 'max' : ''}" style="width:${Math.round((100 * b.v) / max)}%"></div></div><div class="n">${b.v}</div></div>`).join('')}</div>${s.note ? `<div class="note">${t(s.note)}</div>` : ''}`;
  },
  grid: (s) => `${head(s)}<div class="grid">${s.cells.map((c) => `<div class="cell ${c.hi ? 'hi' : ''}"><div class="d">${t(c.top)}</div><b>${t(c.big)}</b><span class="bn lbn">${esc(c.bn)}</span></div>`).join('')}
    <div class="cell end"><b>Shubho Sharodiya</b><span class="bn lbn">শুভ শারদীয়া</span></div></div>`,
  stations: (s) => `${head(s)}<div class="stations">${s.items.map((it) => `<div class="st"><div class="hd"><span class="chip" style="color:${LINE[it.line] || '#CBD5E1'}">${t(it.chip)}</span><b>${t(it.name)}</b></div>
      <ul>${it.rows.map((r) => `<li>${t(r)}</li>`).join('')}</ul></div>`).join('')}</div>`,
  words: (s) => `${head(s)}<div class="words">${s.items.map((it) => `<div class="word"><div class="w">${t(it.name)}<span class="bn">${esc(it.bn)}</span></div><p>${t(it.meta)}</p></div>`).join('')}</div>`,
  cta: (s) => `<div class="kicker">${t(s.kicker || 'Pujo Parikrama 2026')}</div>${ttl(s.big || 'Save it. Send it.', 'big')}
    <div class="mid">${t(s.mid || 'Plan your pujo free: quiet hours, routes, food and metro for every pandal.')}</div>
    <div class="btn">${t(s.btn || 'Link in bio →')}</div><div class="hdl">${esc(HANDLE)}</div>${bnl(s.bn)}`,
  // Wave 1 post types
  word: (s) => `${s.kicker ? `<div class="kicker">${t(s.kicker)}</div>` : ''}${bnl(s.bn)}<div class="title">${t(s.title)}</div>${s.body ? `<div class="body">${t(s.body)}</div>` : ''}`,
  quote: (s) => `${s.kicker ? `<div class="kicker">${t(s.kicker)}</div>` : ''}${bnl(s.bn)}<div class="big-q">${t(s.title)}</div>${s.body ? `<div class="body">${t(s.body)}</div>` : ''}`,
  prompt: (s) => `${s.kicker ? `<div class="kicker">${t(s.kicker)}</div>` : ''}${ttl(s.title)}${bnl(s.bn)}${s.body ? `<div class="body">${t(s.body)}</div>` : ''}${s.foot ? `<div class="tfoot">${t(s.foot)}</div>` : ''}`,
  versus: (s) => `${head(s)}${bnl(s.bn)}<div class="vs">${s.sides.map((x) => `<div><b>${t(x.title)}</b>${x.bn ? `<div class="bn lbn" style="font-size:3.6rem">${esc(x.bn)}</div>` : ''}<p>${t(x.body)}</p></div>`).join('')}</div>${s.foot ? `<div class="tfoot">${t(s.foot)}</div>` : ''}`,
  bingo: (s) => `${head(s)}${bnl(s.bn)}<div class="bingo">${s.cells.map((c) => `<div><span><span class="bn bm">${esc(c.bn)}</span><span class="en">${t(c.en)}</span></span></div>`).join('')}</div>${s.foot ? `<div class="tfoot">${t(s.foot)}</div>` : ''}`,
};
T.split = (s) => `${ttl(s.title)}${s.sub ? `<div class="sub">${t(s.sub)}</div>` : ''}`;
T.cols = (s) => `${ttl(s.title)}${s.sub ? `<div class="sub" style="margin-top:1rem">${t(s.sub)}</div>` : ''}<div class="vs">${s.cols.map((c) => `<div><b class="bn bnh">${esc(c.head)}</b><ul class="cl">${c.items.map((x) => `<li class="bn">${esc(x)}</li>`).join('')}</ul></div>`).join('')}</div>`;
const HERO = new Set(['cover', 'tip', 'cta', 'word', 'quote', 'prompt', 'split']);

function slideHtml(s, W, H) {
  const last = s.page === s.pages;
  const dense = !HERO.has(s.t);
  const cls = [`s-${s.t}`, dense ? 'dense' : 'hero', s.photo || s.photos ? '' : 'nophoto'].join(' ');
  const src = dataUri(s.photo);
  const story = H > 1500;
  const mt = s.t === 'list' ? (s.items.length > 4 ? 250 : 330) : s.t === 'stats' || s.t === 'bars' ? 420 : 300;
  return `<!doctype html><html><head><meta charset="utf-8">${FONTS}<style>${CSS(W, H)}</style></head>
  <body class="${cls}" style="--py:${Math.round((s.py ?? 0.4) * 100)}%;--mt:${story ? mt + 240 : mt}px">
  ${s.photos ? `<div class="two">${s.photos.map((p, k) => `<div><img src="${dataUri(p)}"><span class="bn">${esc(s.labels[k])}</span></div>`).join('')}</div>` : src ? `<img class="ph" src="${src}">` : ''}<div class="sh"></div>
  <div class="top"><div class="mark">পুজো পরিক্রমা<small>${esc(HANDLE)}</small></div>${s.pages > 1 ? `<div class="count">${s.page} / ${s.pages}</div>` : ''}</div>
  ${s.t === 'cover' && s.tag ? `<div class="tag">${t(s.tag)}</div>` : ''}
  <div class="main">${T[s.t](s)}</div>
  <div class="foot"><span class="cred">${s.credit ? 'Photo: ' + esc(s.credit) : ''}</span>${s.pages > 1 ? `<span class="sw">${last ? 'Share ↗' : 'Swipe →'}</span>` : ''}</div>
  </body></html>`;
}

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined });
const pages = new Map();
async function pageFor(W, H) {
  const k = `${W}x${H}`;
  if (!pages.has(k)) pages.set(k, await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 }));
  return pages.get(k);
}
const only = process.env.ONLY ? new RegExp(process.env.ONLY) : null;
const posts = spec.carousels || spec.posts;
const issues = [];
let n = 0;
try {
  for (const c of posts) {
    if (only && !only.test(c.id)) continue;
    const [W, H] = c.size || spec.size || [1080, 1350];
    const page = await pageFor(W, H);
    const out = path.join(dir, c.id);
    mkdirSync(out, { recursive: true });
    for (const [i, s] of c.slides.entries()) {
      s.page ??= i + 1; s.pages ??= c.slides.length;
      if (process.env.DUMP) (await import("node:fs")).writeFileSync(`${process.env.DUMP}-${c.id}-${s.page}.html`, slideHtml(s, W, H));
      await page.setContent(slideHtml(s, W, H), { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForLoadState('load', { timeout: 6000 }).catch(() => {});
      await Promise.race([page.evaluate(() => document.fonts.ready), new Promise((r) => setTimeout(r, 3000))]).catch(() => {});
      // Shrink the root size (all slide type is in rem) until the content fits its box.
      const fit = await page.evaluate((start) => {
        const m = document.querySelector('.main'), root = document.documentElement;
        const over = () => m.scrollHeight > m.clientHeight + 8 || m.scrollWidth > m.clientWidth + 1
          || [...m.querySelectorAll('li, .stat, .cell, .block, .word, .st')].some((e) => e.scrollWidth > e.clientWidth + 1);
        let px = start; root.style.fontSize = px + 'px';
        while (over() && px > 6.5) { px -= 0.25; root.style.fontSize = px + 'px'; }
        return { px, over: over() };
      }, H > 1500 ? 11 : 10);
      await page.evaluate(() => { window.scrollTo(0, 0); document.querySelectorAll('*').forEach((e) => { e.scrollTop = 0; }); });
      if (fit.over || fit.px < 7.5) issues.push(`${c.id} slide ${s.page}: ${fit.over ? 'OVERFLOWS' : 'shrunk'} to ${Math.round(fit.px * 10)}%`);
      await page.screenshot({ path: path.join(out, `slide-${String(s.page).padStart(2, '0')}.jpg`), type: 'jpeg', quality: 90 });
      n++;
    }
  }
} finally {
  await browser.close();
}
console.log(`rendered ${n} slides → ${dir}`);
if (issues.length) console.log('check these slides:\n  ' + issues.join('\n  '));
