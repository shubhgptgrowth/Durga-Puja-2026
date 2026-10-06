// Renders the content kit built by `python -m marketing.kit` into images and print files.
//   node marketing/render.mjs app/kit          → <date>/<card>.jpg (Instagram's API takes JPEG), posters.pdf, flyer.png
//   node marketing/render.mjs --og app/icons   → og.png (1200×630 link preview for WhatsApp/Instagram)
// Cards are plain HTML/CSS screenshotted by Playwright, so Bengali text uses real fonts.
// Commons photos load over the network; if one fails, the card still renders without it.
import { chromium } from 'playwright';
import { readFileSync, mkdirSync, existsSync } from 'node:fs';
import path from 'node:path';
import QRCode from 'qrcode';

const args = process.argv.slice(2);
const og = args[0] === '--og';
const dir = path.resolve(og ? args[1] || 'app/icons' : args[0] || 'app/kit');
const esc = (s = '') => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const SITE_JSON = JSON.parse(readFileSync(path.resolve(path.dirname(new URL(import.meta.url).pathname), '../site.json'), 'utf8'));
const SITE_DISPLAY = (() => { const u = new URL(SITE_JSON.url); return (u.host + u.pathname).replace(/\/$/, ''); })();
// Printed at the foot of cards, posters and the flyer: the Instagram handle while the app lives on github.io.
const FOOTER = SITE_JSON.footer || SITE_DISPLAY;
const SIZE = { post: [1080, 1350], story: [1080, 1920], og: [1200, 630], a4: [794, 1123] };

const FONTS = `<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@500;700&family=Poppins:wght@500;700;800&display=swap" rel="stylesheet">`;
const BASE_CSS = `*{box-sizing:border-box;margin:0}body{font-family:Poppins,"Hind Siliguri","Noto Sans Bengali",system-ui,sans-serif;color:#fff;overflow:hidden}
.bg{position:absolute;inset:0;background:linear-gradient(160deg,#9F1239 0%,#B91C1C 55%,#7C2D12 100%)}
.rings{position:absolute;right:-260px;top:-260px;width:900px;height:900px;border-radius:50%;box-shadow:0 0 0 6px rgba(253,230,138,.16),0 0 0 110px transparent,0 0 0 116px rgba(253,230,138,.12),0 0 0 220px transparent,0 0 0 226px rgba(253,230,138,.08)}
.brand{font-weight:700;color:#FDE68A;font-size:40px;letter-spacing:.3px}
.kicker{font-size:36px;opacity:.9;font-weight:500}
.photo{position:absolute;left:0;right:0;top:0;background-size:cover;background-position:center}
.photo:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.05) 0%,rgba(127,29,29,.55) 60%,#9F1239 100%)}
.credit{position:absolute;right:28px;top:24px;font-size:18px;opacity:.75;max-width:60%;text-align:right;z-index:2}
.photo img{width:100%;height:100%;object-fit:cover;display:block}
.nophoto .photo,.nophoto .credit{display:none}.nophoto .spacer{height:24px!important}
.wrap{position:absolute;inset:0;display:flex;flex-direction:column;overflow:hidden}
.cta{display:inline-block;background:#FDE68A;color:#7F1D1D;font-weight:800;border-radius:999px;padding:26px 56px;font-size:42px}
.url{font-size:28px;opacity:.8}`;

function shell(w, h, body, extra = '') {
  return `<!doctype html><html><head><meta charset="utf-8">${FONTS}<style>${BASE_CSS}${extra}</style></head>
  <body style="width:${w}px;height:${h}px;position:relative">${body}</body></html>`;
}

function photoBlock(ph, h) {
  if (!ph) return '';
  return `<div class="photo" style="height:${h}px"><img src="${esc(ph.src)}" referrerpolicy="no-referrer" onerror="document.body.classList.add('nophoto')"></div><div class="credit">${esc(ph.credit)}</div>`;
}

// Instagram cards: a full-bleed real photo with magazine type on it (same look as marketing/carousels.mjs).
const IG_FONTS = `<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Galada&family=Hind+Siliguri:wght@500;600;700&family=Inter:wght@500;600;700;800&display=swap" rel="stylesheet">`;
const IG_CSS = `body{background:#1a0d0a;font-family:Inter,"Hind Siliguri",system-ui,sans-serif}
.ph{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.sh{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.5) 0%,rgba(0,0,0,0) 16%,rgba(0,0,0,0) 36%,rgba(10,4,2,.75) 60%,rgba(10,4,2,.94) 100%)}
.sh.dense{background:linear-gradient(180deg,rgba(0,0,0,.45) 0%,rgba(0,0,0,0) 12%,rgba(10,4,2,.2) 20%,rgba(10,4,2,.76) 34%,rgba(10,4,2,.9) 50%)}
.nophoto .ph{display:none}.nophoto .sh{background:radial-gradient(120% 80% at 70% 0%,#5b1414 0%,#1a0d0a 60%)}
.mark{font-family:Galada,"Hind Siliguri",cursive;font-size:42px;text-shadow:0 2px 10px rgba(0,0,0,.6)}
.mark small{font-family:Inter,sans-serif;font-size:22px;font-weight:600;opacity:.85;margin-left:14px}
.kick{font-size:26px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#FFC857;display:flex;align-items:center;gap:16px}
.kick:before{content:"";width:50px;height:4px;background:#FFC857}
.ttl{font-family:"DM Serif Display",Georgia,serif;line-height:1.02;margin-top:14px}
.big{font-family:"DM Serif Display",serif;color:#FFC857;line-height:1}
.bnl{font-family:"Hind Siliguri",sans-serif;font-weight:600}
.btn{display:inline-block;background:#fff;color:#1a0d0a;font-weight:800;border-radius:999px}
.cred{position:absolute;left:72px;right:72px;bottom:30px;font-size:19px;opacity:.6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.wrap{text-shadow:0 2px 14px rgba(0,0,0,.45)}`;
const plainTxt = (s = '') => esc(String(s).replace(/[\u{1F000}-\u{1FFFF}☀-➿️‍]/gu, '').trim());

function igShell(w, h, d, body, dense = false, extra = '') {
  const src = d.photo ? String(d.photo.src).split('?')[0].replace(/\/960px-/, '/1280px-') : '';
  const img = d.photo ? `<img class="ph" src="${esc(src)}" data-alt="${esc(d.photo.src)}" onerror="if(!this.dataset.f){this.dataset.f=1;this.src=this.dataset.alt}else{document.body.classList.add('nophoto')}" referrerpolicy="no-referrer">` : '';
  return `<!doctype html><html><head><meta charset="utf-8">${IG_FONTS}<style>${BASE_CSS}${IG_CSS}${extra}</style></head>
  <body class="${d.photo ? '' : 'nophoto'}" style="width:${w}px;height:${h}px;position:relative">${img}<div class="sh${dense ? ' dense' : ''}"></div>${body}
  ${d.photo && d.photo.credit ? `<div class="cred">Photo: ${esc(String(d.photo.credit).replace(/^Photo:\s*/, ''))}</div>` : ''}</body></html>`;
}

function hero(c, [w, h]) {
  const d = c.data, story = c.format === 'story';
  return igShell(w, h, d, `<div class="wrap" style="padding:${story ? 110 : 56}px 72px ${story ? 130 : 84}px">
    <div class="mark">পুজো পরিক্রমা<small>${esc(FOOTER)}</small></div>
    <div style="margin-top:auto">
      <div class="kick">${plainTxt(d.kicker)}</div>
      ${d.big ? `<div class="big" style="font-size:${d.big.length > 3 ? 130 : 230}px;margin-top:10px">${plainTxt(d.big)}</div>` : ''}
      <div class="ttl" style="font-size:${story ? 104 : 92}px">${plainTxt(d.title)}</div>
      ${d.subtitle_bn ? `<p class="bnl" style="font-size:${story ? 44 : 38}px;margin-top:18px;line-height:1.35">${esc(d.subtitle_bn)}</p>` : ''}
      <p style="font-size:${story ? 38 : 32}px;margin-top:14px;line-height:1.38;opacity:.92">${plainTxt(d.subtitle)}</p>
      <span class="btn" style="margin-top:${story ? 54 : 34}px;font-size:${story ? 42 : 34}px;padding:${story ? '24px 54px' : '18px 42px'}">${plainTxt(d.cta || 'Link in bio')}</span>
    </div></div>`);
}

function list(c, [w, h]) {
  const d = c.data, story = c.format === 'story';
  const items = d.items.map((it, i) => `<li>${it.thumb ? `<img class="th" src="${esc(it.thumb)}" referrerpolicy="no-referrer">` : `<span class="n">${i + 1}</span>`}<div><b>${plainTxt(it.name)}${it.name_bn ? ` <span class="bn">${esc(it.name_bn)}</span>` : ''}</b><small>${plainTxt(it.meta)}</small></div></li>`).join('');
  return igShell(w, h, d, `<div class="wrap" style="padding:${story ? 100 : 52}px 72px ${story ? 120 : 76}px">
    <div class="mark">পুজো পরিক্রমা<small>${esc(FOOTER)}</small></div>
    <div style="height:${story ? 380 : 230}px;flex:0 0 auto"></div>
    <div>
      <div class="kick">${plainTxt(d.kicker)}</div>
      <div class="ttl" style="font-size:${story ? 86 : 72}px">${plainTxt(d.title)}</div>
      ${d.subtitle ? `<p style="font-size:${story ? 32 : 28}px;margin-top:10px;opacity:.88;line-height:1.35">${plainTxt(d.subtitle)}</p>` : ''}
    </div>
    <ol>${items}</ol>
    <div style="margin-top:auto;padding-top:18px;display:flex;align-items:center;justify-content:space-between;gap:24px">
      <p style="font-size:${story ? 32 : 26}px;opacity:.9;line-height:1.3">${plainTxt(d.foot || '')}</p>
      <span class="btn" style="flex:0 0 auto;font-size:${story ? 38 : 30}px;padding:${story ? '22px 48px' : '16px 36px'}">${plainTxt(d.cta || 'Link in bio')}</span>
    </div></div>`, true,
  `ol{list-style:none;padding:0;margin-top:${story ? 36 : 24}px;display:flex;flex-direction:column}
   li{display:flex;gap:24px;align-items:center;padding:${story ? 22 : 15}px 0;border-top:1px solid rgba(255,255,255,.24)}
   li:last-child{border-bottom:1px solid rgba(255,255,255,.24)}
   li .th{flex:0 0 auto;width:${story ? 120 : 96}px;height:${story ? 120 : 96}px;border-radius:14px;object-fit:cover;box-shadow:0 4px 14px rgba(0,0,0,.45)}
   li .n{flex:0 0 56px;font-family:"DM Serif Display",serif;font-size:${story ? 60 : 52}px;color:#FFC857;line-height:1}
   li b{font-size:${story ? 40 : 33}px;font-weight:800;display:block;line-height:1.15} li .bn{font-family:'Hind Siliguri';font-weight:600;font-size:${story ? 32 : 27}px;opacity:.88}
   li small{display:block;font-size:${story ? 28 : 23}px;opacity:.8;margin-top:4px}`);
}

async function qr(url, px = 600) {
  return QRCode.toString(url, { type: 'svg', margin: 1, width: px, errorCorrectionLevel: 'M', color: { dark: '#111827', light: '#ffffff' } });
}

async function posterHtml(p) {
  const [w, h] = SIZE.a4, code = await qr(p.url);
  return `<section style="width:${w}px;height:${h}px;position:relative;page-break-after:always;overflow:hidden">
    <div class="bg"></div><div class="rings"></div>
    <div style="position:absolute;inset:0;padding:60px 56px;display:flex;flex-direction:column;align-items:center;text-align:center">
      <div class="brand" style="font-size:30px">🪔 Pujo Parikrama 2026</div>
      <div style="font-size:26px;opacity:.9;margin-top:26px">${p.kind === 'pandal' ? 'You are at' : 'You are eating at'}</div>
      <div style="font-size:52px;font-weight:800;line-height:1.1;margin-top:6px">${esc(p.name)}</div>
      ${p.name_bn ? `<div style="font-family:'Hind Siliguri';font-size:36px;margin-top:4px">${esc(p.name_bn)}</div>` : ''}
      <div style="background:#fff;border-radius:28px;padding:22px;margin-top:34px;width:430px;height:430px">${code.replace('<svg', '<svg width="386" height="386"')}</div>
      <div style="font-size:34px;font-weight:800;margin-top:30px;color:#FDE68A">Scan for crowd times, food,<br>parking &amp; the next pandal</div>
      <div style="font-family:'Hind Siliguri';font-size:28px;margin-top:12px">স্ক্যান করুন: কখন ভিড় কম, কী খাবেন, পরের প্যান্ডেল কোনটা</div>
      <div style="margin-top:auto;font-size:20px;opacity:.85">Free · No sign-up · 🚇 Nearest metro: ${esc(p.metro)}</div>
    </div></section>`;
}

async function flyerHtml(f) {
  const [w, h] = SIZE.post, code = await qr(f.url, 700);
  return shell(w, h, `<div class="bg"></div><div class="rings"></div>
  <div style="position:absolute;inset:0;padding:80px;display:flex;flex-direction:column;align-items:center;text-align:center">
    <div class="brand">🪔 Pujo Parikrama 2026</div>
    <div style="font-size:70px;font-weight:800;line-height:1.08;margin-top:40px">Plan your pandal hopping</div>
    <div style="font-family:'Hind Siliguri';font-size:44px;margin-top:10px">ঠাকুর দেখার প্ল্যান, এক অ্যাপে</div>
    <div style="background:#fff;border-radius:36px;padding:26px;margin-top:46px;width:520px;height:520px">${code.replace('<svg', '<svg width="468" height="468"')}</div>
    <div style="font-size:36px;margin-top:40px;line-height:1.4">${f.pandals} pandals · quiet hours · food · parking<br>metro, bus &amp; auto routes · live check-ins</div>
    <div class="url" style="margin-top:auto">${esc(FOOTER)} · Free</div>
  </div>`);
}

// The link preview for the app (WhatsApp, Instagram DMs): a real protima on the left, the promise on the right.
// The photo is the app's first banner slide (Wikimedia Commons, credited on the image as its licence asks).
const OG_PHOTO = { file: '../app/img/hero-1.jpg', pos: '50% 14%', credit: 'Photo: Tarunsamanta, Wikimedia Commons, CC BY-SA 4.0' };
function ogHtml() {
  const [w, h] = SIZE.og;
  const here = path.dirname(new URL(import.meta.url).pathname);
  const photo = `data:image/jpeg;base64,${readFileSync(path.resolve(here, OG_PHOTO.file)).toString('base64')}`;
  const pandals = (() => { try { return JSON.parse(readFileSync(path.resolve(here, '../app/data/guide.json'), 'utf8')).pandals.length; } catch { return 100; } })();
  const fonts = '<link href="https://fonts.googleapis.com/css2?family=Galada&family=Baloo+Da+2:wght@600;800&family=Poppins:wght@500;700;800&display=swap" rel="stylesheet">';
  return `<!doctype html><html><head><meta charset="utf-8">${fonts}<style>${BASE_CSS}
    .og-photo{position:absolute;left:0;top:0;bottom:0;width:520px;background:url(${photo}) ${OG_PHOTO.pos}/cover}
    .og-photo:after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(0,0,0,0) 55%,#7A0C1A 100%)}
    .og-credit{position:absolute;left:16px;bottom:12px;font-size:15px;opacity:.85;text-shadow:0 1px 3px #000}
    .og-panel{position:absolute;left:520px;right:0;top:0;bottom:0;background:linear-gradient(160deg,#7A0C1A 0%,#9F1239 60%,#7C2D12 100%);
      padding:48px 56px 40px 40px;display:flex;flex-direction:column;border-left:6px solid #F6C343}
    .og-bn{font-family:Galada,"Baloo Da 2",cursive;color:#F6C343;font-size:88px;line-height:1.05}
    .og-en{font-weight:800;font-size:40px;letter-spacing:.5px;margin-top:2px}
    .og-promise{font-family:"Baloo Da 2",Poppins,sans-serif;font-weight:800;font-size:44px;line-height:1.15;margin-top:26px}
    .og-promise small{display:block;font-family:Poppins,sans-serif;font-weight:700;font-size:30px;opacity:.95;margin-top:6px}
    .og-facts{font-size:24px;opacity:.92;margin-top:auto;line-height:1.45}
    .og-url{font-weight:700;color:#FDE68A;font-size:26px;margin-top:8px}</style></head>
  <body style="width:${w}px;height:${h}px;position:relative">
    <div class="og-photo"><div class="og-credit">${esc(OG_PHOTO.credit)}</div></div>
    <div class="og-panel">
      <div class="og-bn">পুজো পরিক্রমা</div>
      <div class="og-en">Pujo Parikrama 2026</div>
      <div class="og-promise">ভিড় এড়িয়ে ঠাকুর দেখুন<small>See every pandal. Skip the queue.</small></div>
      <div class="og-facts">${pandals} Kolkata pandals · when each is quiet · metro &amp; auto · food nearby · free</div>
      <div class="og-url">${esc(SITE_DISPLAY)}</div>
    </div>
  </body></html>`;
}

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined });
const page = await browser.newPage({ deviceScaleFactor: 1 });
const settle = async () => {
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
  await page.evaluate(() => document.fonts.ready).catch(() => {});
};

try {
  if (og) {
    mkdirSync(dir, { recursive: true });
    await page.setViewportSize({ width: SIZE.og[0], height: SIZE.og[1] });
    await page.setContent(ogHtml()); await settle();
    await page.screenshot({ path: path.join(dir, 'og.png') });
    console.log('og.png →', dir);
  } else {
    const kit = JSON.parse(readFileSync(path.join(dir, 'assets.json'), 'utf8'));
    let n = 0;
    const only = process.env.ONLY ? new RegExp(process.env.ONLY) : null;
    for (const c of kit.cards) {
      if (only && !only.test(c.id)) continue;
      const [w, h] = SIZE[c.format];
      await page.setViewportSize({ width: w, height: h });
      await page.setContent((c.template === 'hero' ? hero : list)(c, [w, h]), { timeout: 20000 }); await settle();
      await page.evaluate(() => {
        const wrap = document.querySelector('.wrap'), fits = () => wrap.scrollHeight <= wrap.clientHeight + 1;
        const lis = [...document.querySelectorAll('ol li')];
        while (!fits() && lis.length > 3) lis.pop().remove();
      });
      const file = path.join(dir, c.file); mkdirSync(path.dirname(file), { recursive: true });
      await page.screenshot({ path: file, type: 'jpeg', quality: 90 }); n++;
    }
    if (only) { console.log(`rendered ${n} cards matching ${only}`); process.exit(0); }
    await page.setViewportSize({ width: SIZE.post[0], height: SIZE.post[1] });
    await page.setContent(await flyerHtml(kit.flyer)); await settle();
    await page.screenshot({ path: path.join(dir, 'flyer.png') });
    const sheets = (await Promise.all(kit.posters.map(posterHtml))).join('');
    await page.setContent(`<!doctype html><html><head><meta charset="utf-8">${FONTS}<style>${BASE_CSS}@page{size:A4;margin:0}body{overflow:visible}</style></head><body>${sheets}</body></html>`);
    await settle();
    await page.pdf({ path: path.join(dir, 'posters.pdf'), format: 'A4', printBackground: true, margin: { top: 0, right: 0, bottom: 0, left: 0 } });
    console.log(`rendered ${n} cards, flyer.png and posters.pdf (${kit.posters.length} pages) → ${dir}`);
  }
} finally {
  await browser.close();
}
if (!og && !existsSync(path.join(dir, 'posters.pdf'))) process.exit(1);
