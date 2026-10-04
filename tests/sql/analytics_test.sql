-- Behavioural tests for supabase/migrations/*_analytics.sql (live count, usage events, the analytics directory).
\set ON_ERROR_STOP on
set client_min_messages = warning;

do $$ declare r jsonb; begin
  set local role anon;                                                     -- no sign-in needed
  r := public.track(null, '[]');
  assert r->>'status' = 'no_device', r::text;
  r := public.track('eeeeeeee-0000-0000-0000-000000000001', '[
    {"n": "view", "view": "home", "d": "home"},
    {"n": "place_open", "view": "explore", "place": "t_pandal", "kind": "pandal"},
    {"n": "directions", "view": "explore", "place": "t_pandal", "kind": "pandal"},
    {"n": "place_open", "view": "explore", "place": "park_x", "kind": "parking"},
    {"n": "sfx", "view": "home", "d": "dhak"},
    {"n": "music", "view": "home", "d": "dhak:0"},
    {"n": "BAD NAME", "view": "home"},
    {"n": "view", "view": "home", "d": "home", "t": 1}
  ]');
  assert r->>'status' = 'ok' and (r->>'stored')::int = 7 and (r->>'live')::int = 1, 'junk names dropped: ' || r::text;
  r := public.track('eeeeeeee-0000-0000-0000-000000000002', '[]');           -- a heartbeat
  assert (r->>'live')::int = 2 and (r->>'stored')::int = 0, r::text;
  r := public.site_counts();
  assert (r->>'live')::int = 2, r::text;
  begin perform 1 from public.events; assert false, 'events must not be readable';
  exception when insufficient_privilege then null; end;
  begin perform 1 from analytics.places; assert false, 'the analytics directory must not be readable from the app';
  exception when insufficient_privilege then null; end;
end $$;

do $$ declare r jsonb; n int; begin
  -- A very old timestamp is clamped to the last hour, not trusted.
  assert (select min(at) from public.events) > now() - interval '61 minutes';
  select opens into n from analytics.places where place_id = 't_pandal';
  assert n = 1, 'place opens';
  assert (select directions from analytics.places where place_id = 't_pandal') = 1;
  assert (select kind from analytics.places where place_id = 'park_x') = 'parking', 'parking appears from events alone';
  assert (select taps from analytics.sounds where what = 'dhak' and source = 'sfx') = 1;
  assert (select now_5min from analytics.live) = 2;
  r := public.analytics_report(1);
  assert (r->>'events')::int = 7 and (r->>'people')::int = 1, r::text;
  assert r->'pages'->0->>'page' = 'home' and (r->'pages'->0->>'views')::int = 2, r::text;
  -- Daily cap per device.
  update public.presence set day_events = 1499 where device_id = 'eeeeeeee-0000-0000-0000-000000000001';
  set local role anon;
  r := public.track('eeeeeeee-0000-0000-0000-000000000001', '[{"n": "view"}, {"n": "view"}, {"n": "view"}]');
  assert (r->>'stored')::int = 1, 'cap: ' || r::text;
end $$;

-- Leave other tests' numbers alone.
delete from public.events; delete from public.presence;
select 'analytics SQL tests passed' as result;
