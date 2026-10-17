// ig-dm: comment-to-DM. Whoever comments "PUJO" (or পুজো, route, রুট) on one of our recent Instagram posts gets one
// private reply, plus a short public reply under their comment. Same rules as marketing/engage.py `dm`, which it
// replaces as the main sender: GitHub's 15-minute cron ran only every 4-10 hours, so people waited hours.
//
// The DM is tailored when we can tell which area they want: from the comment itself ("PUJO Behala") or else from
// the post it is on (the Behala route reel's caption names Behala). They get that area's walk: the Metro to start
// from, the pandals in walking order, distance and time, food on the way, and a link that opens exactly that route
// in the app (#plan=…). Otherwise they get the general guide link.
//
// pg_cron calls this every 5 minutes (the `ig-dm-backend` workflow sets that up and the secrets below).
// Only people who asked by commenting are ever messaged, and each comment at most once (public.ig_dm_sent).
// Instagram allows one private reply per comment, within 7 days of the comment, so every post from the last 30 days
// is read (the account posts 10+ a day; the first 30 only went back two days) and its comments from the last 7.
//
// Secrets: IG_USER_ID, IG_ACCESS_TOKEN, IG_PAGE_ID (Facebook-Login tokens send through the Page), DM_CRON_SECRET.
// Deployed with --no-verify-jwt; callers must send the header `x-cron-secret: $DM_CRON_SECRET`.
// ?dry=1 lists who would be messaged, and with what, without sending anything.

const KEYWORDS = ['pujo', 'পুজো', 'পূজো', 'route', 'রুট'];
const DM_BN = 'নমস্কার! 🙏 এই নিন আপনার পুজোর গাইড: মেট্রো থেকে নেমে প্যান্ডেল থেকে প্যান্ডেলে হাঁটার রুট, ' +
  '২০২৬-এর সব থিম এক জায়গায়, আর পথে কোথায় খাবেন। একদম ফ্রি।';
const DM_EN = "Here's your Durga Puja 2026 guide: walk pandal to pandal from the nearest Metro, every 2026 theme in " +
  'one list, and food on the way. Free, no sign-up:';
const SITE = 'https://pujoparikramaguide.in/';
const GUIDE = 'https://pujoparikramaguide.in/?src=ig_dm';
const PUBLIC_REPLY = 'DM-এ পাঠিয়ে দিলাম 💛 Sent to your DMs!';
const ALREADY = 2534023;   // "The comment that you are trying to reply to already has a reply."
// Comments are answered while Instagram allows (7 days from the comment), on posts from the last POST_DAYS: a
// "PUJO" can land on a post long after it went up (the 8 Oct route post kept getting them a week later).
const DAYS = 7, POST_DAYS = 30, MAX_SENDS = 20, MAX_MEDIA_PAGES = 6;

const SB = Deno.env.get('SUPABASE_URL')!;
const KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const db = (path: string, init: RequestInit = {}) =>
  fetch(`${SB}/rest/v1/${path}`, { ...init, headers: { apikey: KEY, Authorization: `Bearer ${KEY}`, 'Content-Type': 'application/json', ...(init.headers || {}) } });
const upsert = (table: string, rows: unknown[]) =>
  db(table, { method: 'POST', headers: { Prefer: 'resolution=merge-duplicates' }, body: JSON.stringify(rows) });

// Words that may sit next to the keyword in a request ("PUJO pls", "send route"). Anything else makes it a normal
// comment: "পুরোনো কলকাতার পুজো 🙌" is praise, not a request, and must not get a DM. Same as engage.py FILLER.
const FILLER = ['pls', 'plz', 'plss', 'please', 'pl', 'send', 'dm', 'me', 'link', 'guide', 'map', 'the', 'a',
  'দিন', 'দাও', 'প্লিজ', 'প্লীজ', 'পাঠান', 'পাঠাও', 'গাইড', 'লিংক',
  'for', 'of', 'to', 'in', 'my', 'i', 'want', 'need', 'can', 'you', 'u', 'us', 'routes', 'list', 'plan',
  'details', 'info', 'share', 'pandal', 'pandals', 'hopping', 'area', 'kolkata', 'hi', 'hello', 'thanks',
  'thank', 'yes', 'interested', 'da', 'dada', 'di', 'didi', 'bhai', 'bro',
  'চাই', 'আমাকে', 'আমায়', 'একটু', 'লিস্ট', 'দয়া', 'করে', 'ধন্যবাদ', 'হ্যাঁ'];
const words = (text = '') => text.toLowerCase().replace(/[^\p{L}\p{M}]+/gu, ' ').trim().split(' ').filter(Boolean);
/** A request has a keyword, and every other word is filler or part of an area or pandal name ("PUJO Behala"). */
export const wantsGuide = (text = '', areaWords: Set<string> = new Set()) => {
  const w = words(text || '');
  return w.some((x) => KEYWORDS.includes(x)) && w.every((x) => KEYWORDS.includes(x) || FILLER.includes(x) || areaWords.has(x));
};

// ---------- areas: which walk does a comment (or the post it is on) mean? ----------
type Area = { phrase: string; zone: string; pandal?: string };
const SPLIT = /\s*(?:[,&:/–—-]|\band\b|\sও\s)\s*/u;
const EXTRA: Record<string, string> = { 'north kolkata': 'north', 'south kolkata': 'south_lakemarket', 'উত্তর কলকাতা': 'north',
  'দক্ষিণ কলকাতা': 'south_lakemarket', 'college street': 'central', 'tollygunge': 'tolly_naktala' };
const SUFFIX = /\s+(sarbojanin(\s+durg\w+)?|durgotsab|durgotsav|puja committee|durga puja)$/i;

export function areaIndex(g: any) {
  const zones = new Map<string, any>(g.zones.filter((z: any) => (z.route?.order || []).length >= 3).map((z: any) => [z.id, z]));
  const out: Area[] = [];
  const add = (phrase: string, zone: string, pandal?: string) => {
    const p = phrase.toLowerCase().trim();
    if (p.length >= 4 && zones.has(zone)) out.push({ phrase: p, zone, pandal });
  };
  for (const z of zones.values()) {
    for (const n of [z.name, z.short, z.name_bn, z.short_bn]) {
      if (!n) continue;
      add(n, z.id);
      n.split(SPLIT).forEach((part: string) => add(part, z.id));
    }
  }
  for (const [p, z] of Object.entries(EXTRA)) add(p, z);
  for (const p of g.pandals) {
    add(p.name.replace(SUFFIX, ''), p.zone, p.id);
    if (p.name_bn) add(p.name_bn, p.zone, p.id);
  }
  out.sort((a, b) => b.phrase.length - a.phrase.length);  // "salt lake" before "lake"
  return { areas: out, words: new Set(out.flatMap((a) => words(a.phrase))), zones };
}

/** The area a text names first ("…Behala & New Alipore pandal hopping route…" → southwest), or null. */
export function findArea(text: string, idx: { areas: Area[] }) {
  const t = ` ${(text || '').toLowerCase().replace(/[^\p{L}\p{M}\d]+/gu, ' ')} `;
  let best: (Area & { at: number }) | null = null;
  for (const a of idx.areas) {
    const at = t.indexOf(` ${a.phrase.replace(/[^\p{L}\p{M}\d]+/gu, ' ')} `);
    if (at >= 0 && (!best || at < best.at)) best = { ...a, at };
  }
  return best;
}

const stationName = (s: any) => s ? s.name.replace(/\s*\((Suburban)\)\s*$/, '').replace(' Sutanuti', '') + (s.line === 'suburban' ? ' station' : ' Metro') : '';
const short = (p: any) => p.name.replace(SUFFIX, '');
const b64u = (s: string) => btoa(String.fromCharCode(...new TextEncoder().encode(s))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

/** The tailored DM for one area: Bengali line, the walk stop by stop, food, and the link that opens that route. */
export function areaDM(g: any, zoneId: string, pandalId?: string) {
  const z = g.zones.find((x: any) => x.id === zoneId);
  const P = new Map(g.pandals.map((p: any) => [p.id, p]));
  const T = new Map(g.transit.map((t: any) => [t.id, t]));
  const F = new Map(g.food.map((f: any) => [f.id, f]));
  const r = z.route;
  const stops = r.order.map((id: string) => P.get(id)).filter(Boolean);
  const st: any = T.get(r.start) || T.get(z.entry_station);
  const list = stops.slice(0, 9).map((p: any, i: number) => `${i + 1}. ${short(p)}`).join('\n') +
    (stops.length > 9 ? `\n…and ${stops.length - 9} more in the app` : '');
  const food = (z.food_ids || []).map((id: string) => F.get(id)).filter(Boolean).slice(0, 2).map((f: any) => f.name);
  // the app's planner fits a route into a time budget: ask for the whole walk (smallest budget it offers that fits),
  // every pandal on it (stars 1+), from 4 pm, so the app shows the same stops as this message
  const need = (r.walk_min || 0) + (r.dwell_min || 0);
  const budget = [240, 360, 600, 720].find((b) => b >= need) || 720;
  const plan = { z: [zoneId], s: st ? `t:${st.id}` : 'me', t: '16:00', r: 1, b: budget };
  const link = `${SITE}?src=ig_dm&a=${zoneId}#plan=${b64u(JSON.stringify(plan))}`;
  const named = pandalId && stops.some((p: any) => p.id === pandalId) ? ` (${short(P.get(pandalId))} is on it)` : '';
  const text = [
    `নমস্কার! 🙏 এই নিন ${z.short_bn || z.name_bn} পুজোর হাঁটার রুট${st ? `, ${stationName(st).replace(' Metro', ' মেট্রো')} থেকে শুরু` : ''}।`,
    '',
    `Your ${z.short} pujo walk${named}: ${stops.length} pandals${st ? `, starting at ${stationName(st)}` : ''}.`,
    list,
    food.length ? `Food on the way: ${food.join(', ')}` : '',
    '',
    'Open it for the timings, distances and directions, stop by stop (free, no sign-up):',
    link,
  ].filter((x, i, a) => x !== '' || a[i - 1] !== '').join('\n');
  return { text, reply: `DM-এ পাঠিয়ে দিলাম 💛 Sent you the ${z.short} route!` };
}

class GraphError extends Error { constructor(public status: number, public body: any) { super(JSON.stringify(body).slice(0, 300)); } }

async function graph(method: 'GET' | 'POST', path: string, token: string, params: Record<string, string> = {}) {
  // Instagram Login tokens ("IG…") only work on graph.instagram.com
  const base = token.startsWith('IG') ? 'https://graph.instagram.com/v21.0' : 'https://graph.facebook.com/v21.0';
  const q = new URLSearchParams({ ...params, access_token: token });
  const r = method === 'GET' ? await fetch(`${base}/${path}?${q}`) : await fetch(`${base}/${path}`, { method, body: q });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new GraphError(r.status, body);
  return body;
}

/** Messages go out through the Facebook Page with the Page's own token; an Instagram-Login token is used as it is. */
async function sendToken(token: string, page: string) {
  if (!page || token.startsWith('IG')) return token;
  try { return (await graph('GET', page, token, { fields: 'access_token' })).access_token || token; } catch { return token; }
}

/** Every post from the last `since` ms, newest first, following the pages. */
async function recentMedia(user: string, token: string, since: number) {
  const out: any[] = [];
  let resp = await graph('GET', `${user}/media`, token, { fields: 'id,timestamp,comments_count,caption', limit: '50' });
  for (let pages = 1; ; pages++) {
    const data = resp.data || [];
    out.push(...data);
    const next = resp.paging?.next;
    if (!next || pages >= MAX_MEDIA_PAGES || !data.length || Date.parse(data[data.length - 1].timestamp) < since) break;
    resp = await (await fetch(next)).json();
  }
  return out.filter((m) => Date.parse(m.timestamp) >= since);
}

Deno.serve(async (req) => {
  const secret = Deno.env.get('DM_CRON_SECRET');
  if (!secret || req.headers.get('x-cron-secret') !== secret) return new Response('forbidden', { status: 403 });
  const dry = new URL(req.url).searchParams.get('dry') === '1';
  const user = Deno.env.get('IG_USER_ID')!, token = Deno.env.get('IG_ACCESS_TOKEN')!, page = Deno.env.get('IG_PAGE_ID') || '';
  const log: string[] = [];
  try {
    const me = (await graph('GET', user, token, { fields: 'username' })).username;
    const since = Date.now() - DAYS * 864e5;
    const media = await recentMedia(user, token, Date.now() - POST_DAYS * 864e5);
    const seen = new Map<string, number>(((await (await db('ig_dm_media?select=media_id,comments_count')).json()) || [])
      .map((m: any) => [m.media_id, m.comments_count]));
    const done = new Set<string>(((await (await db('ig_dm_sent?select=comment_id')).json()) || []).map((r: any) => r.comment_id));
    let g: any = null, idx: ReturnType<typeof areaIndex> | null = null;
    const guide = async () => {  // only fetched when there is a comment to read
      if (!g) {
        try { g = await (await fetch(`${SITE}data/guide.json`)).json(); idx = areaIndex(g); }
        catch (e) { log.push(`guide.json unavailable, sending the general link: ${(e as Error).message}`); g = {}; }
      }
      return idx;
    };
    const send = await sendToken(token, page);
    let sent = 0, already = 0, failed = 0, read = 0;

    for (const m of media) {
      if (!m.comments_count || seen.get(m.id) === m.comments_count) continue;
      read++;
      let ok = true;
      const comments: any[] = [];
      let resp = await graph('GET', `${m.id}/comments`, token, { fields: 'id,text,username,timestamp', limit: '50' });
      for (let pages = 0; ; pages++) {
        comments.push(...(resp.data || []));
        const next = resp.paging?.next || null;
        if (!next || pages >= 5) break;
        resp = await (await fetch(next)).json();
      }
      const ix = await guide();
      for (const c of comments) {
        if (c.username === me || done.has(c.id) || Date.parse(c.timestamp) < since) continue;
        if (!wantsGuide(c.text, ix?.words)) continue;
        const area = ix ? (findArea(c.text, ix) || findArea(m.caption || '', ix)) : null;
        let msg = `${DM_BN}\n\n${DM_EN}\n${GUIDE}`, reply = PUBLIC_REPLY;
        if (area) ({ text: msg, reply } = areaDM(g, area.zone, area.pandal));
        if (dry) {
          log.push(`[dry] would DM @${c.username} (${JSON.stringify((c.text || '').slice(0, 40))}) ${area ? 'the ' + area.zone + ' route' : 'the general link'}`);
          ok = false;
          continue;
        }
        if (sent >= MAX_SENDS) { ok = false; break; }
        try {
          await graph('POST', `${page || user}/messages`, send, {
            recipient: JSON.stringify({ comment_id: c.id }), message: JSON.stringify({ text: msg }),
          });
          await upsert('ig_dm_sent', [{ comment_id: c.id, username: c.username, media_id: m.id, status: 'sent' }]);
          done.add(c.id); sent++;
          log.push(`DM sent to @${c.username}${area ? ` (${area.zone} route)` : ''}`);
          try { await graph('POST', `${c.id}/replies`, token, { message: reply }); }
          catch (e) { log.push(`public reply to @${c.username} failed: ${(e as Error).message}`); }
        } catch (e) {
          if (e instanceof GraphError && e.body?.error?.error_subcode === ALREADY) {
            await upsert('ig_dm_sent', [{ comment_id: c.id, username: c.username, media_id: m.id, status: 'already' }]);
            done.add(c.id); already++;
            log.push(`@${c.username} already has a private reply`);
          } else { ok = false; failed++; log.push(`DM to @${c.username} failed: ${(e as Error).message}`); }
        }
      }
      // Remember the count only when every request on this post was handled, so a failed DM is retried next run.
      if (ok) await upsert('ig_dm_media', [{ media_id: m.id, comments_count: m.comments_count, at: new Date().toISOString() }]);
    }
    const out = { ok: true, dry, posts_in_window: media.length, posts_read: read, sent, already, failed, log };
    console.log(JSON.stringify(out));
    return Response.json(out);
  } catch (e) {
    const out = { ok: false, error: (e as Error).message, log };
    console.error(JSON.stringify(out));
    return Response.json(out, { status: 500 });
  }
});
