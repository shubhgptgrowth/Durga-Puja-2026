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

function hero(c, [w, h]) {
  const d = c.data, story = c.format === 'story', ph = story ? 820 : 560;
  return shell(w, h, `<div class="bg"></div><div class="rings"></div>${photoBlock(d.photo, ph)}
  <div class="wrap" style="padding:${story ? 110 : 80}px 80px">
    <div class="brand">🪔 Pujo Parikrama 2026</div>
    <div style="margin-top:auto">
      <div class="kicker">${esc(d.kicker)}</div>
      <div style="font-size:${d.big?.length > 3 ? 120 : 220}px;font-weight:800;line-height:1;margin:18px 0 6px;color:#FDE68A">${esc(d.big)}</div>
      <div style="font-size:${story ? 84 : 76}px;font-weight:800;line-height:1.08">${esc(d.title)}</div>
      <p style="font-size:${story ? 40 : 34}px;margin-top:26px;line-height:1.35;opacity:.95">${esc(d.subtitle)}</p>
      ${d.subtitle_bn ? `<p style="font-family:'Hind Siliguri';font-size:${story ? 38 : 32}px;margin-top:16px;line-height:1.4;opacity:.9">${esc(d.subtitle_bn)}</p>` : ''}
      <div style="margin-top:${story ? 60 : 40}px;display:flex;align-items:center;justify-content:space-between"><span class="cta">${esc(d.cta || 'Link in bio')}</span></div>
      <div class="url" style="margin-top:28px">${esc(FOOTER)}</div>
    </div></div>`);
}

function list(c, [w, h]) {
  const d = c.data, story = c.format === 'story', ph = d.photo ? (story ? 560 : 380) : 0;
  const items = d.items.map((it, i) => `<li><span class="n">${i + 1}</span><div><b>${esc(it.name)}${it.name_bn ? ` <span class="bn">${esc(it.name_bn)}</span>` : ''}</b><small>${esc(it.meta)}</small></div></li>`).join('');
  return shell(w, h, `<div class="bg"></div><div class="rings"></div>${photoBlock(d.photo, ph)}
  <div class="wrap" style="padding:${story ? 100 : 64}px 72px">
    <div class="brand">🪔 Pujo Parikrama 2026</div>
    <div class="spacer" style="height:${ph ? ph - (story ? 330 : 230) : 24}px;flex:0 0 auto"></div>
    <div>
      <div class="kicker">${esc(d.kicker)}</div>
      <div style="font-size:${story ? 76 : 64}px;font-weight:800;line-height:1.08;margin-top:10px">${esc(d.title)}</div>
      ${d.subtitle ? `<p style="font-size:${story ? 34 : 30}px;margin-top:12px;opacity:.9;line-height:1.35">${esc(d.subtitle)}</p>` : ''}
    </div>
    <ol>${items}</ol>
    <div class="foot" style="margin-top:auto;padding-top:20px">
      <p style="font-size:${story ? 34 : 30}px;opacity:.95;margin-bottom:${story ? 34 : 24}px">${esc(d.foot || '')}</p>
      <span class="cta" style="font-size:${story ? 42 : 36}px;padding:${story ? '26px 56px' : '20px 44px'}">${esc(d.cta || 'Link in bio')}</span>
      <div class="url" style="margin-top:22px">${esc(FOOTER)}</div>
    </div></div>`,
  `ol{list-style:none;padding:0;margin-top:${story ? 44 : 30}px;display:flex;flex-direction:column;gap:${story ? 22 : 16}px}
   li{display:flex;gap:22px;align-items:center;background:rgba(255,255,255,.12);border-radius:26px;padding:${story ? 24 : 18}px 26px}
   li .n{flex:0 0 62px;height:62px;border-radius:50%;background:#FDE68A;color:#7F1D1D;font-weight:800;font-size:32px;display:flex;align-items:center;justify-content:center}
   li b{font-size:${story ? 40 : 34}px;font-weight:700;display:block;line-height:1.15} li .bn{font-family:'Hind Siliguri';font-size:${story ? 32 : 28}px;opacity:.85}
   li small{display:block;font-size:${story ? 28 : 24}px;opacity:.85;margin-top:4px}`);
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

function ogHtml() {
  const [w, h] = SIZE.og;
  return shell(w, h, `<div class="bg"></div><div class="rings" style="right:-360px;top:-420px"></div>
  <div style="position:absolute;inset:0;padding:64px 72px;display:flex;flex-direction:column;justify-content:center">
    <div class="brand" style="font-size:34px">🪔 Durga Puja 2026 · Kolkata</div>
    <div style="font-size:92px;font-weight:800;line-height:1.02;margin-top:14px">Pujo Parikrama</div>
    <div style="font-size:38px;margin-top:18px;opacity:.95">Pandals by area · quiet hours · food · parking · metro, bus &amp; auto</div>
    <div style="font-family:'Hind Siliguri';font-size:34px;margin-top:12px;opacity:.9">ঠাকুর দেখার ফ্রি গাইড · বাংলা ও ইংরেজিতে</div>
  </div>`);
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
