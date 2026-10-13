// ig-dm: comment-to-DM. Whoever comments "PUJO" (or পুজো, route, রুট) on one of our recent Instagram posts gets the
// guide in one private reply, plus a short public reply under their comment. Same rules as marketing/engage.py `dm`,
// which it replaces as the main sender: GitHub's 15-minute cron ran only every 4-10 hours, so people waited hours.
//
// pg_cron calls this every 5 minutes (the `ig-dm-backend` workflow sets that up and the secrets below).
// Only people who asked by commenting are ever messaged, and each comment at most once (public.ig_dm_sent).
// Instagram allows one private reply per comment, within 7 days of it.
//
// Secrets: IG_USER_ID, IG_ACCESS_TOKEN, IG_PAGE_ID (Facebook-Login tokens send through the Page), DM_CRON_SECRET.
// Deployed with --no-verify-jwt; callers must send the header `x-cron-secret: $DM_CRON_SECRET`.
// ?dry=1 lists who would be messaged without sending anything.

const KEYWORDS = ['pujo', 'পুজো', 'পূজো', 'route', 'রুট'];
const DM_BN = 'নমস্কার! 🙏 এই নিন আপনার পুজোর গাইড: মেট্রো থেকে নেমে প্যান্ডেল থেকে প্যান্ডেলে হাঁটার রুট, ' +
  '২০২৬-এর সব থিম এক জায়গায়, আর পথে কোথায় খাবেন। একদম ফ্রি।';
const DM_EN = "Here's your Durga Puja 2026 guide: walk pandal to pandal from the nearest Metro, every 2026 theme in " +
  'one list, and food on the way. Free, no sign-up:';
const GUIDE = 'https://pujoparikramaguide.in/?src=ig_dm';
const PUBLIC_REPLY = 'DM-এ পাঠিয়ে দিলাম 💛 Sent to your DMs!';
const ALREADY = 2534023;   // "The comment that you are trying to reply to already has a reply."
const DAYS = 7, MAX_SENDS = 20;

const SB = Deno.env.get('SUPABASE_URL')!;
const KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const db = (path: string, init: RequestInit = {}) =>
  fetch(`${SB}/rest/v1/${path}`, { ...init, headers: { apikey: KEY, Authorization: `Bearer ${KEY}`, 'Content-Type': 'application/json', ...(init.headers || {}) } });
const upsert = (table: string, rows: unknown[]) =>
  db(table, { method: 'POST', headers: { Prefer: 'resolution=merge-duplicates' }, body: JSON.stringify(rows) });

// Words that may sit next to the keyword in a request ("PUJO pls", "send route"). Anything else makes it a normal
// comment: "পুরোনো কলকাতার পুজো 🙌" is praise, not a request, and must not get a DM. Same as engage.py FILLER.
const FILLER = ['pls', 'plz', 'plss', 'please', 'pl', 'send', 'dm', 'me', 'link', 'guide', 'map', 'the', 'a',
  'দিন', 'দাও', 'প্লিজ', 'প্লীজ', 'পাঠান', 'পাঠাও', 'গাইড', 'লিংক'];
const words = (text = '') => text.toLowerCase().replace(/[^\p{L}\p{M}]+/gu, ' ').trim().split(' ').filter(Boolean);
export const wantsGuide = (text = '') => {
  const w = words(text || '');
  return w.some((x) => KEYWORDS.includes(x)) && w.every((x) => KEYWORDS.includes(x) || FILLER.includes(x));
};

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

Deno.serve(async (req) => {
  const secret = Deno.env.get('DM_CRON_SECRET');
  if (!secret || req.headers.get('x-cron-secret') !== secret) return new Response('forbidden', { status: 403 });
  const dry = new URL(req.url).searchParams.get('dry') === '1';
  const user = Deno.env.get('IG_USER_ID')!, token = Deno.env.get('IG_ACCESS_TOKEN')!, page = Deno.env.get('IG_PAGE_ID') || '';
  const log: string[] = [];
  try {
    const me = (await graph('GET', user, token, { fields: 'username' })).username;
    const since = Date.now() - DAYS * 864e5;
    const media = (await graph('GET', `${user}/media`, token, { fields: 'id,timestamp,comments_count', limit: '30' })).data || [];
    const seen = new Map<string, number>(((await (await db('ig_dm_media?select=media_id,comments_count')).json()) || [])
      .map((m: any) => [m.media_id, m.comments_count]));
    const done = new Set<string>(((await (await db('ig_dm_sent?select=comment_id')).json()) || []).map((r: any) => r.comment_id));
    const send = await sendToken(token, page);
    let sent = 0, already = 0, failed = 0, read = 0;

    for (const m of media) {
      if (Date.parse(m.timestamp) < since || !m.comments_count || seen.get(m.id) === m.comments_count) continue;
      read++;
      let ok = true;
      let next: string | null = null;
      const comments: any[] = [];
      let resp = await graph('GET', `${m.id}/comments`, token, { fields: 'id,text,username,timestamp', limit: '50' });
      for (let pages = 0; ; pages++) {
        comments.push(...(resp.data || []));
        next = resp.paging?.next || null;
        if (!next || pages >= 5) break;
        resp = await (await fetch(next)).json();
      }
      for (const c of comments) {
        if (c.username === me || done.has(c.id) || !wantsGuide(c.text) || Date.parse(c.timestamp) < since) continue;
        if (dry) { log.push(`[dry] would DM @${c.username}: ${JSON.stringify((c.text || '').slice(0, 40))}`); ok = false; continue; }
        if (sent >= MAX_SENDS) { ok = false; break; }
        try {
          await graph('POST', `${page || user}/messages`, send, {
            recipient: JSON.stringify({ comment_id: c.id }), message: JSON.stringify({ text: `${DM_BN}\n\n${DM_EN}\n${GUIDE}` }),
          });
          await upsert('ig_dm_sent', [{ comment_id: c.id, username: c.username, media_id: m.id, status: 'sent' }]);
          done.add(c.id); sent++;
          log.push(`DM sent to @${c.username}`);
          try { await graph('POST', `${c.id}/replies`, token, { message: PUBLIC_REPLY }); }
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
    const out = { ok: true, dry, posts_read: read, sent, already, failed, log };
    console.log(JSON.stringify(out));
    return Response.json(out);
  } catch (e) {
    const out = { ok: false, error: (e as Error).message, log };
    console.error(JSON.stringify(out));
    return Response.json(out, { status: 500 });
  }
});
