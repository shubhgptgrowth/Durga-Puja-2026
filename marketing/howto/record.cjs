// Records the live app on a phone-sized screen, one folder of frames per scene, for the how-to video (compose.py).
//   node record.cjs <outdir> [url]
// Frames come from Chrome's screencast (sharp 780×1688 JPEGs), each named with the time it arrived, so compose.py can
// rebuild real-time motion. Analytics and live-data calls are blocked so the recording leaves no trace in the numbers.
const { chromium } = require(process.env.PLAYWRIGHT || '/usr/local/lib/node_modules/playwright');
const fs = require('fs');

const OUT = process.argv[2] || 'rec';
const URL = process.argv[3] || 'https://pujoparikramaguide.in/';
const W = 390, H = 844, DSF = 2;

const TAP_CSS = `.__tap{position:fixed;z-index:99999;width:46px;height:46px;margin:-23px 0 0 -23px;border-radius:50%;
  background:rgba(255,255,255,.6);border:3px solid rgba(178,24,38,.95);pointer-events:none;animation:__t .65s ease-out forwards}
  @keyframes __t{0%{transform:scale(.45);opacity:1}100%{transform:scale(1.6);opacity:0}}
  .toast{display:none!important}`; // the "dhak is playing" toast would cover the buttons

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: W, height: H }, deviceScaleFactor: DSF, isMobile: true, hasTouch: true,
    locale: 'en-IN', timezoneId: 'Asia/Kolkata',
    geolocation: { latitude: 22.6018, longitude: 88.3655 }, permissions: ['geolocation'],
  });
  await ctx.route(/supabase\.co|google-analytics|googletagmanager|plausible|posthog/, (r) => r.abort());
  const p = await ctx.newPage();
  await p.addInitScript((css) => {
    addEventListener('DOMContentLoaded', () => { const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s); });
    window.__tap = (x, y) => { const d = document.createElement('div'); d.className = '__tap'; d.style.left = x + 'px'; d.style.top = y + 'px'; document.body.appendChild(d); setTimeout(() => d.remove(), 800); };
  }, TAP_CSS);

  const cdp = await ctx.newCDPSession(p);
  let seg = null, n = 0;
  const log = [];
  const save = (buf) => { const t = Date.now() / 1000; fs.writeFileSync(`${OUT}/${seg}/${String(n++).padStart(5, '0')}_${t.toFixed(3)}.jpg`, buf); };
  cdp.on('Page.screencastFrame', (f) => {
    cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {});
    if (seg) save(Buffer.from(f.data, 'base64'));
  });
  const wait = (ms) => p.waitForTimeout(ms);
  const start = async (name) => {
    fs.mkdirSync(`${OUT}/${name}`, { recursive: true }); n = 0;
    seg = name; save(await p.screenshot({ type: 'jpeg', quality: 90 }));
    log.push({ seg: name, t0: Date.now() / 1000 });
  };
  const end = () => { log[log.length - 1].t1 = Date.now() / 1000; seg = null; };
  const tap = async (sel, { click = true, pause = 380 } = {}) => {
    const el = p.locator(sel).first();
    await el.scrollIntoViewIfNeeded();
    const b = await el.boundingBox();
    await p.evaluate(([x, y]) => window.__tap(x, y), [b.x + b.width / 2, b.y + b.height / 2]);
    await wait(pause);
    if (click) await el.click();
  };
  const scroll = async (dy, ms = 1200, target = null) => {
    const steps = Math.round(ms / 33);
    for (let i = 0; i < steps; i++) {
      // ease in-out so it reads like a thumb, not a jump
      const a = (1 - Math.cos(Math.PI * (i + 1) / steps)) / 2 - (1 - Math.cos(Math.PI * i / steps)) / 2;
      await p.evaluate(([d, t]) => { const e = t && document.querySelector(t); (e || window).scrollBy(0, d); }, [dy * a, target]);
      await wait(33);
    }
  };

  await p.goto(URL + '?src=howto_rec', { waitUntil: 'networkidle', timeout: 90000 });
  await wait(2500);
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 88, maxWidth: W * DSF, maxHeight: H * DSF, everyNthFrame: 1 });

  // 1. Home: the festive front page
  await start('home'); await wait(1400); await scroll(330, 1300); await wait(900); end();

  // 2. Plan route: pick areas → build → the ordered walk
  await start('plan');
  await tap('#tab-plan'); await wait(1000);
  await tap('[data-pr="north"]'); await wait(450);
  await tap('[data-pr="central"]'); await wait(650);
  await tap('#planNext'); await wait(1300);
  await tap('#planForm button[type="submit"]'); await wait(1800);
  await scroll(520, 1700); await wait(900);
  end();

  // 3. Explore: least-crowded time on every pandal, then food
  await start('explore');
  await tap('#tab-explore'); await wait(1100);
  await scroll(420, 1500); await wait(800);
  await p.evaluate(() => window.scrollTo(0, 0)); await wait(300);
  await tap('[data-seg="food"]'); await wait(1300);
  await scroll(380, 1300); await wait(700);
  end();

  // 4. A pandal: crowd, timings, how to get there, check in
  await p.evaluate(() => window.scrollTo(0, 0));
  await p.locator('[data-seg="pandals"]').first().click(); await wait(900);
  await start('pandal');
  await tap('#explorePanel [data-place="bagbazar"]'); await wait(1300);
  await tap('#visitBtn', { click: false, pause: 900 }); // show where to check in, without checking in
  await scroll(820, 2600, '#sheet'); await wait(1000);
  end();
  await p.locator('#sheetClose').click().catch(() => {}); await wait(500);

  // 5. My Pujo: steps, pandals, badges
  await start('me');
  await tap('#tab-me'); await wait(1300);
  await tap('#walkBtn', { click: false, pause: 1600 });
  end();

  // 6. বাংলা: the whole app switches language
  await p.locator('#tab-home').click(); await wait(600);
  await p.evaluate(() => window.scrollTo(0, 0)); await wait(400);
  await start('bangla');
  await tap('#langSelect', { click: false, pause: 500 });
  await p.selectOption('#langSelect', 'bn'); await wait(1800);
  await scroll(300, 1100); await wait(800);
  end();

  await cdp.send('Page.stopScreencast');
  fs.writeFileSync(`${OUT}/scenes.json`, JSON.stringify(log, null, 1));
  console.log(log.map((s) => `${s.seg} ${(s.t1 - s.t0).toFixed(1)}s`).join('\n'));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
