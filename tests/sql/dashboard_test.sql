-- Behavioural tests for supabase/migrations/*_dashboard.sql (the team's live dashboard behind a key).
\set ON_ERROR_STOP on
set client_min_messages = warning;

do $$ declare k text; r jsonb; begin
  select key into k from private.dashboard_access;
  assert k is not null and char_length(k) = 64, 'a key is created on install';
  assert (select count(*) from private.dashboard_access) = 1, 're-running the migration keeps one key';
  perform public.track_open('dddddddd-0000-0000-0000-000000000001', 'wa_fwd', 'wa_fwd');
  perform public.track('dddddddd-0000-0000-0000-000000000001', '[{"n": "view", "view": "home", "d": "home"},
    {"n": "place_open", "view": "explore", "place": "t_pandal", "kind": "pandal"},
    {"n": "reel_open", "view": "home", "place": "t_pandal", "kind": "pandal", "d": "ig1:tile"},
    {"n": "reel_watch", "view": "home", "place": "t_pandal", "kind": "pandal", "d": "ig1:90"},
    {"n": "reel_watch", "view": "home", "d": "ig2:99999"},
    {"n": "reel_pandal", "view": "home", "place": "t_pandal", "kind": "pandal", "d": "ig1"}]');

  set local role anon;
  r := public.dashboard(null);
  assert r = '{"ok": false}'::jsonb, 'no key: ' || r::text;
  r := public.dashboard('not-the-key');
  assert r = '{"ok": false}'::jsonb, 'wrong key: ' || r::text;
  r := public.dashboard(k, 7);
  assert (r->>'ok')::boolean and (r->>'days')::int = 7, r::text;
  assert (r->'growth'->>'devices_today')::int >= 1, 'reach: ' || (r->'growth')::text;
  assert r->'growth'->'by_first_source' @> '[{"src": "wa_fwd"}]', 'sources: ' || (r->'growth')::text;
  assert (r->'usage'->>'events')::int >= 2, 'usage: ' || (r->'usage')::text;
  assert jsonb_array_length(r->'hourly') >= 1 and (r->'hourly'->0->>'people')::int >= 1, 'hourly: ' || (r->'hourly')::text;
  assert jsonb_array_length(r->'live_by_page') >= 1, 'online by page: ' || (r->'live_by_page')::text;
  assert r ? 'checkins', r::text;
  assert (r->'reels'->>'opens')::int = 1 and (r->'reels'->>'viewers')::int = 1, 'reel plays: ' || (r->'reels')::text;
  assert (r->'reels'->>'watch_minutes')::numeric = 16.5, 'watch time, each watch capped at 15 min: ' || (r->'reels')::text;
  assert (r->'reels'->>'pandal_taps')::int = 1 and r->'reels'->'top'->0->>'reel' = 'ig2', 'reels: ' || (r->'reels')::text;
  begin perform public.reels_report(1); assert false, 'the reels report is only reachable through the key';
  exception when insufficient_privilege then null; end;
  assert (public.dashboard(k, 100000)->>'days')::int = 90, 'range is capped';
  assert r::text !~ 'dddddddd', 'no device ids leave the database';
  begin perform 1 from private.dashboard_access; assert false, 'the key must not be readable from the app';
  exception when insufficient_privilege then null; end;
  begin perform public.rotate_dashboard_key(); assert false, 'only the team can rotate the key';
  exception when insufficient_privilege then null; end;
end $$;

do $$ declare old text; k text; begin
  select key into old from private.dashboard_access;
  k := public.rotate_dashboard_key();
  assert k <> old and (select key from private.dashboard_access) = k, 'rotate replaces the key';
  set local role anon;
  assert not (public.dashboard(old)->>'ok')::boolean, 'the old link stops working';
  assert (public.dashboard(k)->>'ok')::boolean, 'the new one works';
end $$;

delete from public.events where device_id = 'dddddddd-0000-0000-0000-000000000001';
delete from public.presence where device_id = 'dddddddd-0000-0000-0000-000000000001';
delete from public.app_opens where device_id = 'dddddddd-0000-0000-0000-000000000001';
select 'dashboard SQL tests passed' as result;
