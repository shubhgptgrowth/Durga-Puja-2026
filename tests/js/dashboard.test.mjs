import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { channel, sourceLabel, compact, ticks, num, model, fetchDashboard, CHANNELS } from '../../marketing/dashboard/dashboard.js';

const SAMPLE = {
  ok: true, days: 7, generated_at: '2026-10-08T12:00:00Z',
  growth: {
    devices_total: 1234, devices_today: 210, checked_in_people: 3,
    by_day: [{ day: '2026-10-07', people: 150, new: 90, opens: 300 }, { day: '2026-10-08', people: 210, new: 120, opens: 410 }],
    by_first_source: [{ src: 'wa_fwd', people: 500 }, { src: 'direct', people: 300 }, { src: 'creator_kolkatadelites', people: 40 },
      { src: 'seo_google', people: 30 }, { src: 'rwa_lakegardens', people: 20 }, { src: 'seo_metro', people: 10 }],
    today_by_source: [{ src: 'wa_fwd', people: 100 }],
  },
  usage: { live: { now_5min: 12, last_hour: 40, today: 210, all_time: 1234 }, people: 180, events: 2400,
    pages: [{ page: 'home', views: 900, people: 170 }], places: [{ place_id: 'bagbazar', kind: 'pandal', name: 'Bagbazar Sarbojanin', opens: 30, directions: 9, checkins: 2 }],
    sounds: [{ source: 'sfx', what: 'dhak', taps: 50, people: 20 }], actions: [{ action: 'directions', times: 40, people: 30 }] },
  live_by_page: [{ page: 'explore', people: 7 }],
  hourly: [{ hour: '2026-10-08T17:00:00', people: 25 }],
  checkins: { pandal: 3, food: 1, today: 2 },
};

test('every ?src= code the marketing docs hand out lands in a named channel', () => {
  const docs = ['docs/marketing/COMMUNITY.md', 'docs/marketing/CREATORS.md'].map((p) => readFileSync(new URL(`../../${p}`, import.meta.url), 'utf8')).join('\n');
  const codes = new Set([...docs.matchAll(/src=([a-z0-9_]+)/g)].map((m) => m[1]).filter((c) => !/GROUP|_$/.test(c)));
  assert.ok(codes.size > 10);
  for (const c of codes) assert.notEqual(channel(c), 'Other', c);
  assert.equal(channel('rwa_lakegardens'), 'WhatsApp');
  assert.equal(channel('seo_google'), 'Search & AI');
  assert.equal(channel('seo_metro'), 'Guide pages');
  assert.equal(channel('creator_kolkatadelites'), 'Creators');
  assert.equal(channel('fb_behala_residents'), 'Communities');
  assert.ok(CHANNELS.includes(channel('anything_else')));
});

test('codes read as words', () => {
  assert.equal(sourceLabel('creator_kolkatadelites'), 'Creator · kolkatadelites');
  assert.equal(sourceLabel('fb_behala_residents'), 'Facebook group · behala residents');
  assert.equal(sourceLabel('wa_fwd'), 'WhatsApp forwards');
});

test('numbers: Indian grouping, compact ticks, clean axis steps', () => {
  assert.equal(num(123456), '1,23,456');
  assert.equal(compact(950), '950');
  assert.equal(compact(1200), '1.2K');
  assert.equal(compact(150000), '1.5L');
  assert.deepEqual(ticks(37), [0, 10, 20, 30, 40]);
  assert.deepEqual(ticks(0), [0, 1]);
  assert.ok(ticks(1234).at(-1) >= 1234);
});

test('model: reach, deltas, channels and series from one reply', () => {
  const d = model(SAMPLE);
  assert.equal(d.live.now, 12);
  assert.equal(d.reach.total, 1234);
  assert.equal(d.reach.vsYesterday, 60);
  assert.equal(d.reach.newToday, 120);
  assert.equal(d.perDay[1].returning, 90);
  assert.equal(d.perDay[1].label, '8 Oct');
  assert.equal(d.channels[0].name, 'WhatsApp');
  assert.equal(d.channels[0].people, 520);   // wa_fwd + rwa_lakegardens
  assert.equal(d.hourly[0].label, '17:00');
  assert.equal(d.places[0].name, 'Bagbazar Sarbojanin');
  assert.equal(d.actions[0].name, 'Directions taps');
  assert.equal(model({ ok: true }).reach.vsYesterday, null);   // an empty project still renders
});

test('fetchDashboard posts the key and treats a refusal as denied', async () => {
  let sent;
  const ok = await fetchDashboard({ url: 'https://x.supabase.co', anonKey: 'anon' }, 'k1', 7,
    async (url, init) => { sent = { url, init }; return { ok: true, json: async () => SAMPLE }; });
  assert.equal(ok.days, 7);
  assert.equal(sent.url, 'https://x.supabase.co/rest/v1/rpc/dashboard');
  assert.deepEqual(JSON.parse(sent.init.body), { p_key: 'k1', p_days: 7 });
  await assert.rejects(fetchDashboard({ url: 'u', anonKey: 'a' }, 'bad', 7, async () => ({ ok: true, json: async () => ({ ok: false }) })), /denied/);
});
