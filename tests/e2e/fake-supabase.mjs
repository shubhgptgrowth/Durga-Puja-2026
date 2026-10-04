// In-memory stand-in for the parts of Supabase the app uses (Auth anonymous sign-in, PostgREST
// views and RPCs, and Storage). It mirrors the rules in supabase/migrations closely enough for
// end-to-end tests. CI also runs the same suite against a real local Supabase stack.
import http from 'node:http';
import { readFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';

const R = 6371000, rad = (d) => (d * Math.PI) / 180;
const distance = (a, b) => { const h = Math.sin(rad(b[0] - a[0]) / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(rad(b[1] - a[1]) / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(h)); };
const istDay = (d = new Date()) => new Date(d.getTime() + 5.5 * 3600e3).toISOString().slice(0, 10);

export function startFakeSupabase({ guidePath, port = 0 }) {
  const g = JSON.parse(readFileSync(guidePath, 'utf8'));
  const places = new Map([...g.pandals.map((p) => [p.id, { ...p, kind: 'pandal' }]), ...g.food.map((f) => [f.id, { ...f, kind: 'food' }])]);
  const db = { tokens: new Map(), visits: [], photos: [], likes: new Set(), reports: new Set(), files: new Map(), opens: new Map(), ratings: new Map(), profiles: new Map(), events: [], presence: new Map(), offline: false };

  const json = (res, code, body) => { res.writeHead(code, { 'Content-Type': 'application/json', ...cors }); res.end(JSON.stringify(body)); };
  const cors = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'apikey, authorization, content-type, x-upsert, cache-control, prefer', 'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS' };
  const body = (req) => new Promise((r) => { const c = []; req.on('data', (d) => c.push(d)); req.on('end', () => r(Buffer.concat(c))); });
  const uidOf = (req) => db.tokens.get((req.headers.authorization || '').replace(/^Bearer /, '')) || null;
  const issue = (uid) => { const tok = 'tok-' + randomUUID(); db.tokens.set(tok, uid); return { access_token: tok, refresh_token: 'ref-' + uid, token_type: 'bearer', expires_in: 3600, user: { id: uid } }; };

  const stats = () => [...places.values()].map((p) => {
    const v = db.visits.filter((x) => x.place_id === p.id);
    return { place_id: p.id, kind: p.kind, visits: v.length, today: v.filter((x) => x.day === istDay()).length,
      last_hour: v.filter((x) => Date.now() - x.at < 3600e3).length, photos: db.photos.filter((x) => x.place_id === p.id && !x.hidden).length };
  });
  const near = (p, lat, lng, acc) => { const d = distance([lat, lng], [p.lat, p.lng]); return [d, d <= p.checkin_radius_m + Math.min(Math.max(acc ?? 50, 0), 100)]; };

  const TAGS = ['tasty', 'value', 'quick', 'clean', 'friendly', 'crowded', 'pricey', 'slow'];
  const ratingStats = () => {
    const by = {};
    for (const [k, r] of db.ratings) { const id = k.split('|')[0]; (by[id] ||= []).push(r); }
    return Object.entries(by).map(([place_id, rs]) => {
      const n = {}; rs.forEach((r) => r.tags.forEach((t) => (n[t] = (n[t] || 0) + 1)));
      return { place_id, rating: Math.round((rs.reduce((a, r) => a + r.stars, 0) / rs.length) * 10) / 10, ratings: rs.length,
        top_tags: Object.keys(n).sort((a, b) => n[b] - n[a] || a.localeCompare(b)).slice(0, 3) };
    });
  };
  const clean = (x) => (x == null || !String(x).trim() ? 'direct' : /^[a-z0-9_]{1,40}$/.test(String(x).trim().toLowerCase()) ? String(x).trim().toLowerCase() : 'other');
  const rpc = {
    track_open(uid, a) {
      if (!a.p_device) return { status: 'no_device' };
      const k = a.p_device + '|' + istDay(), row = db.opens.get(k);
      if (row) { row.opens++; return { status: 'repeat', day: istDay() }; }
      db.opens.set(k, { src: clean(a.p_src), first_src: clean(a.p_first_src ?? a.p_src), opens: 1 });
      return { status: 'counted', day: istDay() };
    },
    record_visit(uid, a) {
      const p = places.get(a.p_place); if (!p) return { status: 'unknown_place' };
      const at = a.p_at ? new Date(a.p_at) : new Date();
      if (Date.now() - at > 12 * 3600e3) return { status: 'expired' };
      if (a.p_lat == null) return { status: 'no_location' };
      const [d, ok] = near(p, a.p_lat, a.p_lng, a.p_accuracy);
      if (!ok) return { status: 'too_far', distance_m: Math.round(d) };
      if (db.visits.filter((x) => x.user === uid && Date.now() - x.at < 3600e3).length >= 40) return { status: 'rate_limited' };
      const day = istDay(at);
      const dup = db.visits.some((x) => x.user === uid && x.place_id === p.id && x.day === day);
      if (!dup) db.visits.push({ user: uid, place_id: p.id, day, at: at.getTime() });
      const s = stats().find((x) => x.place_id === p.id);
      return { status: dup ? 'duplicate' : 'counted', distance_m: Math.round(d), today: s.today, visits: s.visits };
    },
    track(uid, a) {
      if (!a.p_device) return { status: 'no_device' };
      db.presence.set(a.p_device, Date.now());
      const ok = (a.p_events || []).slice(0, 50).filter((e) => /^[a-z_]{1,24}$/.test(e.n || ''));
      db.events.push(...ok.map((e) => ({ device: a.p_device, name: e.n, view: e.view, place: e.place, kind: e.kind, detail: e.d })));
      return { status: 'ok', stored: ok.length, live: [...db.presence.values()].filter((x) => Date.now() - x < 300e3).length + (db.extraLive || 0) };
    },
    site_counts() {
      const live = [...db.presence.values()].filter((x) => Date.now() - x < 300e3).length + (db.extraLive || 0);
      return { live, today: db.presence.size + (db.extraLive || 0), people: db.opens.size + (db.extraPeople || 0) };
    },
    rate_place(uid, a) {
      if (!places.has(a.p_place)) return { status: 'unknown_place' };
      if (!(a.p_stars >= 1 && a.p_stars <= 5)) return { status: 'bad_stars' };
      if (!db.visits.some((x) => x.user === uid && x.place_id === a.p_place)) return { status: 'visit_first' };
      db.ratings.set(a.p_place + '|' + uid, { stars: a.p_stars, tags: [...new Set((a.p_tags || []).filter((t) => TAGS.includes(t)))].slice(0, 3) });
      return { status: 'ok', ...ratingStats().find((r) => r.place_id === a.p_place) };
    },
    save_profile(uid, a) {
      if (!a.p_consent) { db.profiles.delete(uid); return { status: 'deleted' }; }
      const d = String(a.p_phone || '').replace(/\D/g, '').replace(/^(91|0)(?=[6-9]\d{9}$)/, '');
      if (!/^[6-9]\d{9}$/.test(d)) return { status: 'bad_phone' };
      db.profiles.set(uid, { name: (a.p_name || '').trim().slice(0, 60) || null, phone: '+91' + d, lang: a.p_lang, first_src: a.p_src, device_id: a.p_device });
      return { status: 'ok' };
    },
    add_photo(uid, a) {
      const p = places.get(a.p_place); if (!p) return { status: 'unknown_place' };
      if (!a.p_path.startsWith(uid + '/') || !a.p_thumb_path.startsWith(uid + '/')) return { status: 'bad_path' };
      if (!db.files.has(a.p_path)) return { status: 'not_uploaded' };
      const on = a.p_lat != null && near(p, a.p_lat, a.p_lng, a.p_accuracy)[1];
      const row = { id: randomUUID(), user: uid, place_id: p.id, media_type: a.p_media_type, path: a.p_path, thumb_path: a.p_thumb_path,
        caption: (a.p_caption || '').trim().slice(0, 140) || null, on_site: on, likes: 0, reports: 0, hidden: false, created_at: new Date().toISOString() };
      db.photos.push(row);
      return { status: 'ok', id: row.id, on_site: on };
    },
    toggle_like(uid, a) {
      const ph = db.photos.find((x) => x.id === a.p_photo && !x.hidden); if (!ph) return { status: 'not_found' };
      const k = ph.id + uid, liked = !db.likes.has(k);
      liked ? db.likes.add(k) : db.likes.delete(k); ph.likes += liked ? 1 : -1;
      return { status: 'ok', liked, likes: ph.likes };
    },
    report_photo(uid, a) {
      const k = a.p_photo + uid; if (db.reports.has(k)) return { status: 'already_reported' };
      db.reports.add(k); const ph = db.photos.find((x) => x.id === a.p_photo);
      if (ph) { ph.reports++; ph.hidden ||= ph.reports >= 3; }
      return { status: 'ok', hidden: !!ph?.hidden };
    },
    delete_photo(uid, a) {
      const i = db.photos.findIndex((x) => x.id === a.p_photo && x.user === uid); if (i < 0) return { status: 'not_found' };
      const [ph] = db.photos.splice(i, 1);
      return { status: 'ok', path: ph.path, thumb_path: ph.thumb_path };
    },
  };

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://x');
    if (req.method === 'OPTIONS') { res.writeHead(204, cors); return res.end(); }
    if (db.offline && !url.pathname.startsWith('/__')) { req.socket.destroy(); return; }
    const p = url.pathname;
    if (p === '/__crowd') { db.extraLive = +url.searchParams.get('live') || 0; db.extraPeople = +url.searchParams.get('people') || 0; return json(res, 200, {}); }
    if (p === '/__state') return json(res, 200, { events: db.events, ratings: db.ratings.size, profiles: [...db.profiles.values()], visits: db.visits.length, photos: db.photos.length, files: db.files.size, opens: [...db.opens.values()] });
    if (p === '/__offline') { db.offline = url.searchParams.get('on') === '1'; return json(res, 200, { offline: db.offline }); }
    if (!req.headers.apikey && !p.startsWith('/storage/v1/object/public/')) return json(res, 401, { message: 'no apikey' });

    if (p === '/auth/v1/signup' && req.method === 'POST') return json(res, 200, issue(randomUUID()));
    if (p === '/auth/v1/token' && req.method === 'POST') {
      const b = JSON.parse(await body(req)); const uid = String(b.refresh_token || '').replace(/^ref-/, '');
      return uid ? json(res, 200, issue(uid)) : json(res, 400, { error: 'invalid_grant' });
    }
    if (p === '/rest/v1/place_stats') return json(res, 200, stats());
    if (p === '/rest/v1/place_rating_stats') return json(res, 200, ratingStats());
    if (p === '/rest/v1/traffic_notices') return json(res, 200, [{ title: 'Traffic arrangements for Durga Puja 2026', url: 'https://kolkatatrafficpolice.gov.in/puja2026.pdf', first_seen: '2026-10-10T06:00:00Z' }]);
    if (p === '/rest/v1/photos_feed') {
      const uid = uidOf(req); let rows = db.photos.filter((x) => !x.hidden);
      const pid = url.searchParams.get('place_id');
      if (pid?.startsWith('eq.')) rows = rows.filter((x) => x.place_id === pid.slice(3));
      if (pid?.startsWith('in.(')) { const set = new Set(pid.slice(4, -1).split(',')); rows = rows.filter((x) => set.has(x.place_id)); }
      if (url.searchParams.get('on_site') === 'is.true') rows = rows.filter((x) => x.on_site);
      const lt = url.searchParams.get('created_at'); if (lt?.startsWith('lt.')) rows = rows.filter((x) => x.created_at < lt.slice(3));
      rows = rows.sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, +(url.searchParams.get('limit') || 30));
      return json(res, 200, rows.map(({ user, reports, hidden, ...r }) => ({ ...r, mine: user === uid, liked: db.likes.has(r.id + uid) })));
    }
    if (p.startsWith('/rest/v1/rpc/') && req.method === 'POST') {
      const name = p.slice('/rest/v1/rpc/'.length), uid = uidOf(req);
      if (!uid && !['track_open', 'track', 'site_counts'].includes(name)) return json(res, 401, { message: 'JWT required' });  // granted to anon
      const fn = rpc[name]; if (!fn) return json(res, 404, { message: 'no such function' });
      return json(res, 200, fn(uid, JSON.parse(await body(req) || '{}')));
    }
    if (p.startsWith('/storage/v1/object/public/moments/')) {
      const f = db.files.get(decodeURIComponent(p.slice('/storage/v1/object/public/moments/'.length)));
      if (!f) { res.writeHead(404, cors); return res.end(); }
      res.writeHead(200, { 'Content-Type': f.type, ...cors }); return res.end(f.buf);
    }
    if (p.startsWith('/storage/v1/object/moments/') && req.method === 'POST') {
      const uid = uidOf(req), path = decodeURIComponent(p.slice('/storage/v1/object/moments/'.length));
      if (!uid || !path.startsWith(uid + '/')) return json(res, 403, { message: 'new row violates row-level security policy' });
      if (db.files.has(path)) return json(res, 409, { message: 'exists' });
      db.files.set(path, { buf: await body(req), type: req.headers['content-type'] });
      return json(res, 200, { Key: 'moments/' + path });
    }
    if (p === '/storage/v1/object/moments' && req.method === 'DELETE') {
      const uid = uidOf(req), b = JSON.parse(await body(req));
      for (const k of b.prefixes || []) if (k.startsWith(uid + '/')) db.files.delete(k);
      return json(res, 200, []);
    }
    json(res, 404, { message: 'not found: ' + p });
  });
  return new Promise((resolve) => server.listen(port, '127.0.0.1', () => resolve({ url: `http://127.0.0.1:${server.address().port}`, anonKey: 'fake-anon-key', server, db })));
}
