// traffic-fetch: collect Kolkata Traffic Police notices about the pujo into public.traffic_notices.
//
// kolkatatrafficpolice.gov.in doesn't answer requests from outside India, so this must run in Mumbai.
// Callers pin the region with the header `x-region: ap-south-1` (the pg_cron job and the workflow do).
// It only reads public pages and stores links to the police's own documents; it never rewrites them.
// Deployed with --no-verify-jwt; a 20-minute throttle keeps it from hitting the police site more often.

const BASE = 'https://kolkatatrafficpolice.gov.in/';
const PAGES = ['', 'notification.php', 'notifications.php', 'notice.php', 'trafficadvisory.php', 'advisory.php', 'whatsnew.php', 'news.php'];
const PUJA = /puja|pujo|durga|mahalaya|immersion|bisarjan|visarjan|festiv|carnival|sharod|navaratri|navratri/i;
const NOTICE = /traffic|arrangement|restriction|regulation|diversion|advisory|notification|notice|one[- ]?way|parking/i;
const THROTTLE_MIN = 20;

const SB = Deno.env.get('SUPABASE_URL')!;
const KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const db = (path: string, init: RequestInit = {}) =>
  fetch(`${SB}/rest/v1/${path}`, { ...init, headers: { apikey: KEY, Authorization: `Bearer ${KEY}`, 'Content-Type': 'application/json', ...(init.headers || {}) } });

const decode = (s: string) => s.replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/&nbsp;/g, ' ').replace(/&#39;|&rsquo;/g, "'").replace(/&quot;/g, '"').replace(/\s+/g, ' ').trim();

function links(html: string, page: string) {
  const out: { url: string; title: string }[] = [];
  for (const m of html.matchAll(/<a\b[^>]*href\s*=\s*["']([^"'#]+)["'][^>]*>([\s\S]*?)<\/a>/gi)) {
    try {
      const url = new URL(m[1].trim(), page).href;
      if (!/^https?:/.test(url)) continue;
      const title = decode(m[2]) || decodeURIComponent(url.split('/').pop() || '');
      out.push({ url, title: title.slice(0, 300) });
    } catch { /* bad href */ }
  }
  return out;
}

Deno.serve(async (req) => {
  const region = Deno.env.get('SB_REGION') || req.headers.get('x-sb-edge-region') || '';
  const force = new URL(req.url).searchParams.get('force') === '1';
  // Throttle: skip if a run happened recently (unless forced from the workflow).
  if (!force) {
    const last = await db('traffic_fetch_log?select=at&order=at.desc&limit=1').then((r) => r.json()).catch(() => []);
    if (last[0] && Date.now() - Date.parse(last[0].at) < THROTTLE_MIN * 60e3) {
      return Response.json({ skipped: true, last: last[0].at, region });
    }
  }
  const pages: Record<string, string | number> = {};
  const found = new Map<string, { url: string; title: string; page: string; relevant: boolean }>();
  for (const p of PAGES) {
    const page = new URL(p, BASE).href;
    try {
      const r = await fetch(page, { headers: { 'User-Agent': 'PujoParikrama/1.0 (+https://shubhgptgrowth.github.io/Durga-Puja-2026/)' }, signal: AbortSignal.timeout(20000) });
      pages[page] = r.status;
      if (!r.ok) continue;
      for (const l of links(await r.text(), page)) {
        const text = `${l.title} ${l.url}`;
        const isDoc = /\.pdf($|\?)/i.test(l.url) || NOTICE.test(text);
        if (!isDoc) continue;
        found.set(l.url, { ...l, page, relevant: PUJA.test(text) });
      }
    } catch (e) {
      pages[page] = String((e as Error).message || e).slice(0, 80);
    }
  }
  const rows = [...found.values()].map((x) => ({ ...x, last_seen: new Date().toISOString() }));
  let error: string | null = null;
  if (rows.length) {
    const r = await db('traffic_notices?on_conflict=url', { method: 'POST', headers: { Prefer: 'resolution=merge-duplicates,return=minimal' }, body: JSON.stringify(rows) });
    if (!r.ok) error = `upsert ${r.status}: ${(await r.text()).slice(0, 200)}`;
  }
  const reached = Object.values(pages).some((s) => s === 200);
  const relevant = rows.filter((x) => x.relevant).length;
  await db('traffic_fetch_log', { method: 'POST', headers: { Prefer: 'return=minimal' },
    body: JSON.stringify({ ok: reached && !error, region, pages, links: rows.length, relevant, error }) });
  return Response.json({ ok: reached && !error, region, pages, links: rows.length, relevant, error,
    sample: rows.filter((x) => x.relevant).slice(0, 10).map((x) => x.title) });
});
