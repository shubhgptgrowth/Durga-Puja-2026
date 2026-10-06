/* Shared state, the data index, and formatting helpers used by every view. */
import { hav, crowdIndex as crowdCore, strideM, kcalFor as kcalCore } from './core.js';
import { makeT } from './i18n.js';
import { CONFIG } from './config.js';
import { Community } from './community.js';

const SYNCED = new Set(['history', 'checkins', 'prefs', 'myMoments']);
export const store = {
  get(k, d) { try { const v = localStorage.getItem('pp:' + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) {
    try { localStorage.setItem('pp:' + k, JSON.stringify(v)); } catch { /* private mode */ }
    if (SYNCED.has(k)) document.dispatchEvent(new CustomEvent('pp:dirty')); // sync.js backs these up
  },
  clear() { try { Object.keys(localStorage).filter((k) => k.startsWith('pp:')).forEach((k) => localStorage.removeItem(k)); } catch { /* ignore */ } },
};

export const G = { data: null };               // guide bundle (data/guide.json)
export const idx = { pandal: {}, food: {}, parking: {}, transit: {}, zone: {}, region: {}, day: {} };
const DEFAULT_PREFS = { height: 165, weight: 65, goal: 10000, lowData: false, motion: true, lang: 'en', consent: false };
export const S = {
  view: 'home', day: null, hour: new Date().getHours(), me: null,
  prefs: { ...DEFAULT_PREFS, ...store.get('prefs', {}) },
  checkins: store.get('checkins', {}),   // pandalId -> {ts, how, community}
  history: store.get('history', {}),     // YYYY-MM-DD -> {m, ms, steps, pandals: [], foods: []}
  car: store.get('car', null),
  plan: store.get('activePlan', null),
  explore: { seg: 'pandals', region: 'all', area: 'all', sort: 'popular', food: new Set(), mode: 'list' },
  moments: { region: 'all', area: 'all', onSite: false, items: [], done: false, loading: false },
  walk: null,
};
export const community = new Community(CONFIG.community);

export const t = makeT(() => S.prefs.lang);
export const bn = () => S.prefs.lang === 'bn';
export const savePrefs = () => store.set('prefs', S.prefs);

export function loadGuide(g) {
  G.data = g;
  const src = { pandal: 'pandals', zone: 'zones', region: 'regions', food: 'food', parking: 'parking', transit: 'transit' };
  for (const [k, key] of Object.entries(src)) for (const r of g[key]) idx[k][r.id] = r;
  for (const d of g.meta.days) idx.day[d.id] = d;
}

/* ---------------- model ---------------- */
export const ll = (r) => [r.lat, r.lng];
export const M = () => G.data.meta.model;
export const walkM = (a, b) => hav(a, b) * M().detour;
export const crowdIndex = (base, df, hour) => crowdCore(M().hour_factors, base, df, hour);
export const dayFactor = () => idx.day[S.day].factor;
export const crowdNow = (p, hour = S.hour) => crowdIndex(p.crowd_base, dayFactor(), hour);
export const crowdLevel = (c) => (c < 25 ? 'quiet' : c < 50 ? 'moderate' : c < 75 ? 'busy' : 'packed');
export const crowdWord = (c) => t('crowd.' + crowdLevel(c));
export const crowdColor = (c) => `var(--c-${crowdLevel(c)})`;
export const stride = () => strideM(S.prefs.height, M().stride_factor);
export const stepsFor = (m) => Math.round(m / stride());
export const kcalFor = (walkMin, queueMin = 0, brisk = false) =>
  kcalCore({ walkMin, queueMin, weightKg: S.prefs.weight, met: brisk ? M().met_brisk : M().met_stroll, queueMet: M().queue_met });

/* ---------------- names (language-aware) ---------------- */
export const nm = (p) => (bn() && p.name_bn) || p.name;
export const zn = (z) => (bn() && z.name_bn) || z.name;
export const zs = (z) => (bn() && z.short_bn) || z.short;
const DAY_HI = { mahalaya: 'महालया', panchami: 'पंचमी', shashthi: 'षष्ठी', saptami: 'सप्तमी', ashtami: 'अष्टमी', navami: 'नवमी', dashami: 'दशमी' };
export const dn = (d) => (bn() && d.name_bn) || (S.prefs.lang === 'hi' && DAY_HI[d.id]) || d.name;
/** Locale for dates and numbers in the current UI language. */
export const loc = () => ({ bn: 'bn-IN', hi: 'hi-IN' })[S.prefs.lang] || 'en-IN';
export const zoneOf = (id) => idx.zone[id];
export const placeOf = (id) => idx.pandal[id] || idx.food[id] || null;
export const placeKind = (id) => (idx.pandal[id] ? 'pandal' : idx.food[id] ? 'food' : null);

/* ---------------- formatting ---------------- */
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const fmt = (n) => Math.round(n).toLocaleString('en-IN');
export const km = (m) => (m / 1000).toFixed(m < 10000 ? 2 : 1);
export const dist = (m) => (m < 1000 ? `${Math.round(m / 10) * 10} m` : `${km(m)} km`);
export function ampm(h) {
  h = ((h % 24) + 24) % 24;
  if (!bn()) return `${h % 12 || 12} ${h < 12 ? 'am' : 'pm'}`;
  const part = h < 4 ? 'রাত' : h < 6 ? 'ভোর' : h < 12 ? 'সকাল' : h < 16 ? 'দুপুর' : h < 18 ? 'বিকেল' : h < 20 ? 'সন্ধে' : 'রাত';
  return `${part} ${h % 12 || 12}টা`;
}
export const todayKey = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
export const btn = (attrs = '') => `role="button" tabindex="0" ${attrs}`;
// Headings are set in type, not emoji: strip any emoji a translation carries.
export const plain = (s) => String(s).replace(/[\p{Extended_Pictographic}\u{1F1E6}-\u{1F1FF}]\uFE0F?/gu, '').replace(/\s{2,}/g, ' ').trim();
export const icon = (name, cls = '') => `<svg class="ic ${cls}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
export const bnDigits = (s) => (bn() ? String(s).replace(/\d/g, (c) => '০১২৩৪৫৬৭৮৯'[c]) : String(s));
