/* The team dashboard's data layer (/kit/dashboard/, docs/product/ANALYTICS.md): it fetches public.dashboard() and
 * turns the reply into what the page draws. No DOM here, so tests/js can check it. */

export const GOAL = 100000;   // the reach goal before the pujas (docs/marketing/STRATEGY.md)

const LABELS = {
  direct: 'Direct / typed / home screen', ig_bio: 'Instagram bio link', ig_story: 'Instagram story link',
  ig_mycard: 'My Pujo card shares', wa_channel: 'WhatsApp Channel', wa_fwd: 'WhatsApp forwards',
  wa_place: 'WhatsApp place shares', wa_plan: 'WhatsApp plan shares', wa_metro: 'WhatsApp · metro page',
  wa_night: 'WhatsApp · late-night page', wa_quiz: 'WhatsApp · quiz', wa_parikrama: 'WhatsApp · WBTC page',
  share: 'Share button', plan_share: 'Shared routes', qr_flyer: 'QR flyer', other: 'Other',
  seo_google: 'Google search', seo_bing: 'Bing search', seo_other: 'Other search engines',
  ai_answer: 'AI answers (ChatGPT, Perplexity…)', guide_direct: 'Guide page, no referrer',
  reddit_kolkata: 'Reddit r/kolkata', quora: 'Quora',
};

const PREFIXES = [
  ['creator_', 'Creator'], ['committee_', 'Puja committee'], ['press_', 'Press'], ['ref_', 'Link from'],
  ['qr_', 'QR poster'], ['fb_', 'Facebook group'], ['rwa_', 'Housing society'], ['office_', 'Office group'],
  ['college_', 'College group'], ['wa_', 'WhatsApp'], ['ig_', 'Instagram'], ['seo_', 'Guide page'],
];

/** A ?src= code as a person would say it: 'creator_kolkatadelites' → 'Creator · kolkatadelites'. */
export function sourceLabel(src) {
  if (LABELS[src]) return LABELS[src];
  const p = PREFIXES.find(([k]) => src.startsWith(k));
  return p ? `${p[1]} · ${src.slice(p[0].length).replace(/_/g, ' ')}` : src;
}

export const CHANNELS = ['WhatsApp', 'Instagram', 'Search & AI', 'Guide pages', 'Communities', 'Creators',
  'QR & committees', 'Press & other sites', 'Shares', 'Direct', 'Other'];

/** Which channel a ?src= code belongs to (the codes are listed in docs/marketing/COMMUNITY.md and CREATORS.md). */
export function channel(src) {
  if (src === 'direct') return 'Direct';
  if (/^(wa_|rwa_|office_|college_)/.test(src)) return 'WhatsApp';
  if (src.startsWith('ig_')) return 'Instagram';
  if (/^seo_(google|bing|other)$/.test(src) || src === 'ai_answer') return 'Search & AI';
  if (src.startsWith('seo_') || src === 'guide_direct') return 'Guide pages';
  if (/^(reddit|fb_|quora)/.test(src)) return 'Communities';
  if (src.startsWith('creator_')) return 'Creators';
  if (/^(qr_|committee_)/.test(src)) return 'QR & committees';
  if (/^(press_|ref_)/.test(src)) return 'Press & other sites';
  if (src === 'share' || src === 'plan_share') return 'Shares';
  return 'Other';
}

const ACTIONS = {
  directions: 'Directions taps', transit: 'Transit route taps', checkin: 'Check-in / ate-here taps', rate: 'Ratings',
  share: 'Shares', filter: 'Filter & sort changes', lang: 'Language switches', plan: 'Routes built',
  trail: 'Ready-made trails opened', moment: 'Moments posted', install: 'Installs to home screen',
};
export const actionLabel = (a) => ACTIONS[a] || a;

/** 123456 → '1,23,456' (Indian grouping, as the team reads numbers). */
export const num = (n) => Math.round(Number(n) || 0).toLocaleString('en-IN');

/** Short form for axis ticks and tight labels: 950, 1.2K, 12K, 1.2L. */
export function compact(n) {
  n = Number(n) || 0;
  if (n >= 1e5) return `${+(n / 1e5).toFixed(n >= 1e6 ? 0 : 1)}L`;
  if (n >= 1e3) return `${+(n / 1e3).toFixed(n >= 1e4 ? 0 : 1)}K`;
  return String(Math.round(n));
}

/** Clean axis ticks from 0 to at least max: steps of 1, 2 or 5 × 10^k. */
export function ticks(max, count = 4) {
  if (!(max > 0)) return [0, 1];
  const raw = max / count, mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  const out = [];
  for (let v = 0; v < max + step * 0.999; v += step) out.push(Math.round(v * 1e6) / 1e6);
  return out;
}

/** '2026-10-08' → '8 Oct' */
export function dayLabel(iso) {
  const [, m, d] = iso.slice(0, 10).split('-').map(Number);
  return `${d} ${['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][m - 1]}`;
}

/** Everything the page draws, from one dashboard() reply. */
export function model(r) {
  const g = r.growth || {}, u = r.usage || {}, live = u.live || {};
  const days = (g.by_day || []).map((d) => ({ day: d.day, label: dayLabel(d.day), total: d.people, new: d.new, returning: Math.max(0, d.people - d.new), opens: d.opens }));
  const today = days.at(-1), yesterday = days.at(-2);
  const sources = (g.by_first_source || []).map((s) => ({ src: s.src, label: sourceLabel(s.src), channel: channel(s.src), people: s.people }));
  const byChannel = new Map(CHANNELS.map((c) => [c, 0]));
  for (const s of sources) byChannel.set(s.channel, byChannel.get(s.channel) + s.people);
  return {
    generatedAt: r.generated_at, days: r.days,
    live: { now: live.now_5min || 0, hour: live.last_hour || 0, today: live.today || 0 },
    reach: { total: g.devices_total || 0, today: g.devices_today || 0, goal: GOAL, share: Math.min(1, (g.devices_total || 0) / GOAL),
      newToday: today ? today.new : 0, vsYesterday: today && yesterday ? today.total - yesterday.total : null,
      checkedIn: g.checked_in_people || 0 },
    checkins: r.checkins || { pandal: 0, food: 0, today: 0 },
    perDay: days,
    hourly: (r.hourly || []).map((h) => ({ hour: h.hour, label: `${Number(String(h.hour).slice(11, 13))}:00`, people: h.people })),
    channels: [...byChannel].map(([name, people]) => ({ name, people })).filter((c) => c.people > 0).sort((a, b) => b.people - a.people),
    sources,
    todaySources: (g.today_by_source || []).map((s) => ({ src: s.src, label: sourceLabel(s.src), people: s.people })),
    pages: (u.pages || []).map((p) => ({ name: p.page, views: p.views, people: p.people })),
    onlineByPage: (r.live_by_page || []).map((p) => ({ name: p.page, people: p.people })),
    places: (u.places || []).map((p) => ({ name: p.name || p.place_id, kind: p.kind || '', opens: p.opens, directions: p.directions, checkins: p.checkins })),
    actions: (u.actions || []).map((a) => ({ name: actionLabel(a.action), times: a.times, people: a.people })).sort((a, b) => b.times - a.times),
    sounds: (u.sounds || []).map((s) => ({ name: `${s.source === 'sfx' ? 'Tap pad' : 'Radio'} · ${s.what}`, taps: s.taps, people: s.people })),
    period: { people: u.people || 0, events: u.events || 0 },
  };
}

/** Calls public.dashboard(); resolves to the raw reply. Throws 'denied' for a wrong key. */
export async function fetchDashboard({ url, anonKey }, key, days, fetchImpl = fetch) {
  const res = await fetchImpl(`${url}/rest/v1/rpc/dashboard`, {
    method: 'POST',
    headers: { apikey: anonKey, Authorization: `Bearer ${anonKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ p_key: key, p_days: days }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const r = await res.json();
  if (!r || !r.ok) throw new Error('denied');
  return r;
}
