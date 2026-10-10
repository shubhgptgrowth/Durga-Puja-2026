import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  hav, orderRoute, pathLen, crowdIndex, stepsFor, kcalFor, judgeFix, StepDetector,
  routeUrls, isOpen, hhmm, encodePlan, decodePlan, parseSteps, mergeProgress, embedUrl,
} from '../../app/core.js';
import { dietMatch, hasEgg, cost2 } from '../../app/foodinfo.js';
import { STR } from '../../app/i18n.js';

const G = JSON.parse(readFileSync(new URL('../../app/data/guide.json', import.meta.url)));
const ll = (r) => [r.lat, r.lng];

test('haversine matches a known distance', () => {
  assert.ok(Math.abs(hav([22.5640, 88.3510], [22.5175, 88.3462]) - 5195) < 300);
});

test('JS route order matches the Python pipeline for every zone', () => {
  const P = Object.fromEntries(G.pandals.map((p) => [p.id, p]));
  const T = Object.fromEntries(G.transit.map((s) => [s.id, s]));
  for (const z of G.zones) {
    const members = z.pandal_ids.map((id) => P[id]);
    const order = orderRoute(ll(T[z.route.start]), members.map(ll)).map((i) => members[i].id);
    assert.deepEqual(order, z.route.order, z.id);
  }
});

test('2-opt never makes a route longer than nearest-neighbour', () => {
  const start = [22.52, 88.35];
  const stops = G.pandals.filter((p) => p.zone === 'south_lakemarket').map(ll);
  const order = orderRoute(start, stops);
  assert.deepEqual([...order].sort((a, b) => a - b), [...stops.keys()]);
  assert.ok(pathLen([start, ...order.map((i) => stops[i])]) <= pathLen([start, ...stops]));
});

test('crowd index matches the pipeline formula and stays bounded', () => {
  const hf = G.meta.model.hour_factors;
  assert.ok(crowdIndex(hf, 5, 1.1, 6) < crowdIndex(hf, 5, 1.1, 20));
  for (let h = -3; h < 30; h++) { const c = crowdIndex(hf, 5, 1.1, h); assert.ok(c >= 0 && c <= 100); }
  const p = G.pandals[0];
  assert.equal(crowdIndex(hf, p.crowd_base, 1.1, 20), p.peak_crowd);
});

test('fitness maths agree with pipeline/fitness.py', () => {
  assert.equal(stepsFor(1000, 165, 0.415), Math.round(1000 / (1.65 * 0.415)));
  assert.equal(kcalFor({ walkMin: 60, weightKg: 65, met: 3.0 }), 195);
  const it = G.itineraries.find((i) => i.id === 'north_heritage');
  assert.equal(stepsFor(it.totals.walk_m, 165, 0.415), it.totals.steps);
});

test('GPS filter rejects noise and vehicles and accepts walking', () => {
  const a = { lat: 22.5185, lng: 88.3489, t: 0, accuracy: 8 };
  assert.equal(judgeFix(null, a).use, false);
  assert.equal(judgeFix(a, { ...a, accuracy: 60, t: 5000 }).reason, 'inaccurate');
  assert.equal(judgeFix(a, { ...a, lat: a.lat + 0.00001, t: 5000 }).reason, 'jitter');          // ~1 m
  assert.equal(judgeFix(a, { ...a, lat: a.lat + 0.0009, t: 5000 }).reason, 'vehicle');           // 100 m in 5 s
  const ok = judgeFix(a, { ...a, lat: a.lat + 0.00009, t: 8000 });                               // 10 m in 8 s
  assert.equal(ok.use, true);
  assert.ok(Math.abs(ok.dist - 10) < 1);
});

function simulate(det, { hz = 50, seconds = 10, stepHz = 1.9, amp = 2.5, noise = 0.15 }) {
  let rnd = 42; const rand = () => ((rnd = (rnd * 16807) % 2147483647) / 2147483647 - 0.5) * 2;
  for (let i = 0; i < hz * seconds; i++) {
    const tms = (i * 1000) / hz;
    const z = 9.81 + amp * Math.sin(2 * Math.PI * stepHz * (tms / 1000)) + noise * rand();
    det.push(0.2 * rand(), 0.2 * rand(), z, tms);
  }
  return det.total;
}

test('step detector counts a 1.9 Hz walking cadence', () => {
  const steps = simulate(new StepDetector(), { seconds: 20 });
  assert.ok(Math.abs(steps - 38) <= 3, `got ${steps}`);
});

test('step detector counts gentle walking with the phone in the hand', () => {
  for (const amp of [0.9, 1.2]) {
    const steps = simulate(new StepDetector(), { seconds: 20, amp, noise: 0.3 });
    assert.ok(Math.abs(steps - 38) <= 3, `amp ${amp}: got ${steps}`);
  }
});

test('step detector ignores sensor noise and a single bump', () => {
  assert.equal(simulate(new StepDetector(), { amp: 0, noise: 0.8 }), 0, 'a shaky hand while standing');
  assert.equal(simulate(new StepDetector(), { amp: 0, noise: 0.3 }), 0);
  const d = new StepDetector();
  for (let i = 0; i < 100; i++) d.push(0, 0, 9.81 + (i === 50 ? 6 : 0), i * 20);
  assert.equal(d.total, 0);
});

test('Google Maps legs never exceed 3 waypoints and chain end to start', () => {
  const pts = Array.from({ length: 11 }, (_, i) => [22.5 + i / 1000, 88.3]);
  const legs = routeUrls(pts);
  assert.equal(legs.length, 3);
  for (const u of legs) {
    const w = new URL(u).searchParams.get('waypoints');
    assert.ok(!w || w.split('|').length <= 3);
  }
  assert.equal(new URL(legs[0]).searchParams.get('destination'), new URL(legs[1]).searchParams.get('origin'));
  assert.equal(new URL(legs[2]).searchParams.get('destination'), pts[10].join(','));
});

test('opening hours handle ranges that cross midnight', () => {
  const at = (h, m = 0) => new Date(2026, 9, 18, h, m);
  assert.equal(isOpen('12:00-23:00', at(13)), true);
  assert.equal(isOpen('12:00-23:00', at(23, 30)), false);
  assert.equal(isOpen('16:00-01:00', at(0, 30)), true);
  assert.equal(isOpen('16:00-01:00', at(10)), false);
});

test('hhmm wraps past midnight', () => {
  assert.equal(hhmm(25 * 60 + 5), '01:05');
  assert.equal(hhmm(-30), '23:30');
});

test('plan share links round-trip and reject junk', () => {
  const p = { z: ['north', 'central'], s: 't:shyambazar', t: '22:00', r: 5, b: 600, k: 1, d: 'ashtami' };
  assert.deepEqual(decodePlan(encodePlan(p)), p);
  assert.equal(decodePlan('not-base64!!'), null);
  assert.equal(decodePlan(encodePlan({ z: [], s: 'x' })), null);
});

test('every English UI string has a Bengali translation and the same placeholders', () => {
  const ph = (s) => (s.match(/\{\w+\}/g) || []).sort().join();
  for (const [k, v] of Object.entries(STR.en)) {
    for (const lang of ['bn', 'hi']) {
      assert.ok(STR[lang][k], `missing ${lang}: ${k}`);
      assert.equal(ph(STR[lang][k]), ph(v), `placeholder mismatch (${lang}): ${k}`);
    }
  }
});

test('bundle has Bengali names for every pandal, zone and day', () => {
  // Neighbourhood pujas discovered from OSM fall back to their English name when OSM has no name:bn.
  for (const p of G.pandals) if (p.geo_source !== 'osm-discovered') assert.ok(p.name_bn, p.id);
  for (const z of G.zones) assert.ok(z.name_bn && z.short_bn, z.id);
  for (const d of G.meta.days) assert.ok(d.name_bn, d.id);
});

/* ---------------- community-era helpers ---------------- */
import { fmtCount, timeAgo, searchEntries, nearest } from '../../app/core.js';
import { readdirSync } from 'node:fs';

test('fmtCount compacts large numbers', () => {
  assert.deepEqual([0, 999, 1000, 1234, 9999, 25300, 1250000].map(fmtCount), ['0', '999', '1k', '1.2k', '9.9k', '25k', '1.2M']);
});

test('timeAgo buckets', () => {
  const now = Date.parse('2026-10-18T12:00:00Z');
  assert.deepEqual(timeAgo('2026-10-18T11:59:30Z', now), { n: 0, unit: 'now' });
  assert.deepEqual(timeAgo('2026-10-18T11:15:00Z', now), { n: 45, unit: 'm' });
  assert.deepEqual(timeAgo('2026-10-18T07:00:00Z', now), { n: 5, unit: 'h' });
  assert.deepEqual(timeAgo('2026-10-16T12:00:00Z', now), { n: 2, unit: 'd' });
});

test('search finds pandals by English prefix, Bengali name, and dish', () => {
  const entries = [
    ...G.pandals.map((p) => ({ id: p.id, kind: 'pandal', names: [p.name, p.name_bn], extra: p.tags, boost: p.popularity })),
    ...G.food.map((f) => ({ id: f.id, kind: 'food', names: [f.name], extra: f.dishes })),
  ];
  assert.equal(searchEntries(entries, 'tridh')[0].id, 'tridhara');
  assert.equal(searchEntries(entries, 'ত্রিধারা')[0].id, 'tridhara');
  assert.ok(searchEntries(entries, 'kabiraji').some((e) => e.id === 'mitra_cafe'));
  assert.deepEqual(searchEntries(entries, 'x'), []);
});

test('nearest returns places sorted by distance within a radius', () => {
  const p = G.pandals.find((x) => x.id === 'tridhara');
  const n = nearest([p.lat, p.lng], G.pandals, { maxM: 1500, limit: 4 });
  assert.equal(n[0].place.id, 'tridhara');
  assert.ok(n.every((x, i) => i === 0 || x.distance >= n[i - 1].distance));
  assert.ok(n.every((x) => x.distance <= 1500));
});

test('check-in radius in the app bundle matches the server seed', () => {
  const seed = readFileSync(new URL('../../supabase/seed.sql', import.meta.url), 'utf8');
  for (const p of [...G.pandals, ...G.food]) {
    const m = seed.match(new RegExp(`\\('${p.id}', '[a-z]+', '(?:[^']|'')*', '[a-z_]+', ([\\d.]+), ([\\d.]+), (\\d+)\\)`));
    assert.ok(m, `${p.id} missing from seed.sql`);
    assert.equal(+m[3], p.checkin_radius_m, `${p.id} radius`);
    assert.ok(Math.abs(+m[1] - p.lat) < 1e-6 && Math.abs(+m[2] - p.lng) < 1e-6, `${p.id} coordinates`);
  }
});

test('every translation key used in the app exists in both languages', () => {
  const dir = new URL('../../app/', import.meta.url);
  const files = [...readdirSync(dir).filter((f) => f.endsWith('.js')).map((f) => new URL(f, dir)),
    ...readdirSync(new URL('views/', dir)).map((f) => new URL('views/' + f, dir))];
  const used = new Set();
  for (const f of files) {
    const src = readFileSync(f, 'utf8');
    for (const m of src.matchAll(/\bt\(\s*'([a-zA-Z0-9_.]+)'\s*[,)]/g)) used.add(m[1]);
    for (const m of src.matchAll(/\bt\([^()]*\?\s*'([a-zA-Z0-9_.]+)'\s*:\s*'([a-zA-Z0-9_.]+)'/g)) { used.add(m[1]); used.add(m[2]); }
  }
  for (const m of readFileSync(new URL('index.html', dir), 'utf8').matchAll(/data-i18n="([^"]+)"/g)) used.add(m[1]);
  // Families built dynamically ('slot.' + id, ...): every member must exist.
  const families = {
    'slot.': Object.keys(G.meta.slots), 'crowd.': ['quiet', 'moderate', 'busy', 'packed'], 'car.': ['ok', 'limited', 'avoid'],
    'adv.': ['ok', 'limited', 'avoid'], 'type.': [...new Set(G.food.map((f) => f.type))], 'diet.': ['veg', 'nonveg', 'both', 'egg'],
    'kind.': [...new Set(G.parking.map((p) => p.kind))], 'cap.': [...new Set(G.parking.map((p) => p.capacity))], 'mode.': ['any', 'walk', 'metro', 'bus', 'auto', 'car'], 'kindLabel.': ['pandal', 'food', 'parking'], 'ago.': ['m', 'h', 'd'],
    'sort.': ['popular', 'quiet', 'near', 'live'], 'stars.': ['1', '3', '4', '5'], 'budget.': ['120', '180', '240', '360', '600'],
    'ff.': ['veg', 'nonveg', 'egg', 'sweets', 'street', 'open'], 'hs.ios': ['1', '2', '3', '4'],
    'rt.': ['tasty', 'value', 'quick', 'clean', 'friendly', 'crowded', 'pricey', 'slow'], 'm.err.': ['too_big', 'too_long', 'unsupported', 'server'],
    'b.': ['first', 'five', 'fifteen', 'thirty', 'zone', 'k10', 'ashtami', 'dawn', 'owl', 'foodie', 'ns', 'goal', 'lens'],
  };
  for (const [prefix, ids] of Object.entries(families)) for (const id of ids) used.add(prefix + id);
  const missing = [...used].filter((k) => !STR.en[k] || !STR.bn[k] || !STR.hi[k]);
  assert.deepEqual(missing, [], 'missing translations');
});

test('iPhone Shortcut step links', () => {
  assert.deepEqual(parseSteps('8432', '2026-10-18'), { n: 8432, date: '2026-10-18' });
  assert.deepEqual(parseSteps('8%2C432.6', '2026-10-18'), { n: 8433, date: '2026-10-18' });
  assert.deepEqual(parseSteps('500000&date=2026-10-17', '2026-10-18'), { n: 100000, date: '2026-10-17' });
  assert.equal(parseSteps('12&date=2026-10-30', '2026-10-18').date, '2026-10-18', 'future dates fall back to today');
  assert.equal(parseSteps('abc', '2026-10-18'), null);
  assert.equal(parseSteps('-5', '2026-10-18').n, 5, 'a stray minus sign is ignored, not negative');
});

test('food diet filters, egg detection and cost for two', () => {
  const roll = { veg: 'both', dishes: ['Egg roll'], type: 'street', price: 1 };
  const sweets = { veg: 'veg', dishes: ['Sandesh'], type: 'sweets', price: 1 };
  const cabin = { veg: 'nonveg', dishes: ['Fish kabiraji', 'Mughlai paratha'], type: 'cabin', price: 2 };
  assert.ok(hasEgg(roll) && hasEgg(cabin) && !hasEgg(sweets));
  assert.ok(!hasEgg({ veg: 'both', dishes: ['Biryani', 'Dimsum'], type: 'restaurant', price: 2 }), 'dimsum is not dim (egg)');
  const pick = (...d) => [roll, sweets, cabin].filter((f) => dietMatch(f, new Set(d)));
  assert.deepEqual(pick(), [roll, sweets, cabin]);
  assert.deepEqual(pick('veg'), [sweets]);
  assert.deepEqual(pick('nonveg'), [roll, cabin]);
  assert.deepEqual(pick('egg'), [roll, cabin]);
  assert.deepEqual(pick('veg', 'egg'), [roll, sweets, cabin], 'several chips = any of them');
  assert.equal(cost2(roll), 150);
  assert.equal(cost2(cabin), 500);
  assert.equal(cost2({ ...cabin, cost2: 650 }), 650, 'a checked cost2 wins');
  for (const f of G.food) assert.ok(cost2(f) >= 100 && cost2(f) <= 3000, f.id);
});

test('My Pujo progress from two browsers merges without losing anything', () => {
  const phone = { history: { '2026-10-18': { m: 3000, ms: 1, steps: 4200, pandals: ['a', 'b'], foods: ['x'] } }, checkins: { a: { ts: 200 }, b: { ts: 300 } }, name: 'Rina', goal: 12000, myMoments: 1 };
  const laptop = { history: { '2026-10-18': { m: 1000, ms: 5, steps: 9000, health: 9500, pandals: ['c'], foods: [] }, '2026-10-17': { m: 10, ms: 1, steps: 5, pandals: [], foods: [] } },
    checkins: { a: { ts: 100 }, c: { ts: 400 } }, name: '', myMoments: 3, myRatings: { x: { stars: 5 } } };
  const m = mergeProgress(phone, laptop);
  const d = m.history['2026-10-18'];
  assert.deepEqual([d.m, d.ms, d.steps, d.health], [3000, 5, 9000, 9500]);
  assert.deepEqual(d.pandals.sort(), ['a', 'b', 'c']);
  assert.ok(m.history['2026-10-17'], 'days only one side has are kept');
  assert.deepEqual(Object.keys(m.checkins).sort(), ['a', 'b', 'c']);
  assert.equal(m.checkins.a.ts, 100, 'earliest check-in time wins');
  assert.equal(m.name, 'Rina'); assert.equal(m.goal, 12000); assert.equal(m.myMoments, 3);
  assert.deepEqual(m.myRatings, { x: { stars: 5 } });
  assert.deepEqual(mergeProgress(m, m), mergeProgress(m, {}), 'merging the same backup again changes nothing');
});

test('Pujo Reels: only Instagram, Facebook and YouTube links get a player, each through its official embed', () => {
  assert.equal(embedUrl('https://www.instagram.com/reel/Cx12abc_D-/?igsh=abc'), 'https://www.instagram.com/reel/Cx12abc_D-/embed/');
  assert.equal(embedUrl('https://www.instagram.com/p/Cx12abcD/'), 'https://www.instagram.com/p/Cx12abcD/embed/');
  assert.equal(embedUrl('https://www.youtube.com/shorts/dQw4w9WgXcQ'), 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?autoplay=1&playsinline=1&rel=0');
  assert.match(embedUrl('https://www.facebook.com/watch/?v=123'), /^https:\/\/www\.facebook\.com\/plugins\/video\.php\?href=https%3A%2F%2Fwww\.facebook\.com%2Fwatch%2F%3Fv%3D123&/);
  for (const bad of ['http://www.instagram.com/reel/Cx12abc/', 'https://evil.example/reel/Cx12abc/', 'javascript:alert(1)', '', null,
    'https://www.instagram.com/reel/Cx12abc/"><script>', 'https://www.facebook.com/x" onload="alert(1)']) {
    const u = embedUrl(bad);
    assert.ok(u === null || !/["<> ]/.test(u), String(bad));
  }
  assert.equal(embedUrl('https://evil.example/reel/Cx12abc/'), null);
});

test('Pujo Reels feed file: every reel the deploy publishes can be played', () => {
  const f = JSON.parse(readFileSync(new URL('../../app/data/reels.json', import.meta.url)));
  assert.ok(Array.isArray(f.reels));
  for (const r of f.reels) assert.ok(embedUrl(r.url), r.url);
});
