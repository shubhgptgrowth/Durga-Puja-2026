import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  hav, orderRoute, pathLen, crowdIndex, stepsFor, kcalFor, judgeFix, StepDetector,
  routeUrls, isOpen, hhmm, encodePlan, decodePlan,
} from '../../app/core.js';
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

test('step detector ignores sensor noise and a single bump', () => {
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
    assert.ok(STR.bn[k], `missing bn: ${k}`);
    assert.equal(ph(STR.bn[k]), ph(v), `placeholder mismatch: ${k}`);
  }
});

test('bundle has Bengali names for every pandal, zone and day', () => {
  for (const p of G.pandals) assert.ok(p.name_bn, p.id);
  for (const z of G.zones) assert.ok(z.name_bn && z.short_bn, z.id);
  for (const d of G.meta.days) assert.ok(d.name_bn, d.id);
});
