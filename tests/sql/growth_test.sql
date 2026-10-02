-- Behavioural tests for supabase/migrations/*_growth.sql (reach measurement).
\set ON_ERROR_STOP on
set client_min_messages = warning;

do $$ declare r jsonb; begin
  set local role anon;                                              -- no sign-in needed
  r := public.track_open(null, 'ig_bio');
  assert r->>'status' = 'no_device', r::text;

  r := public.track_open('aaaaaaaa-0000-0000-0000-000000000001', 'ig_bio', 'ig_bio');
  assert r->>'status' = 'counted', r::text;
  r := public.track_open('aaaaaaaa-0000-0000-0000-000000000001', 'wa_share', 'ig_bio');
  assert r->>'status' = 'repeat', 'one row per device per day';

  r := public.track_open('aaaaaaaa-0000-0000-0000-000000000002', 'QR_Suruchi_Sangha', null);  -- normalised to lower case
  assert r->>'status' = 'counted', r::text;
  r := public.track_open('aaaaaaaa-0000-0000-0000-000000000003', '<script>', '');               -- junk → other / direct
  assert r->>'status' = 'counted', r::text;
end $$;

-- The app can't read the table or the report.
do $$ begin
  set local role anon;
  begin perform 1 from public.app_opens; assert false, 'app_opens must not be readable';
  exception when insufficient_privilege then null; end;
  begin perform public.growth_report(); assert false, 'growth_report must not be callable by the app';
  exception when insufficient_privilege then null; end;
end $$;

do $$ declare g jsonb; begin
  g := public.growth_report();
  assert (g->>'devices_total')::int = 3 and (g->>'devices_today')::int = 3, g::text;
  assert (select (e->>'opens')::int from jsonb_array_elements(g->'by_day') e limit 1) = 4, g::text;
  assert g->'by_first_source' @> '[{"src": "ig_bio", "people": 1}, {"src": "qr_suruchi_sangha", "people": 1}, {"src": "direct", "people": 1}]', g::text;
  assert g->'today_by_source' @> '[{"src": "other", "people": 1}]', g::text;
  assert g->'today_by_source' @> '[{"src": "ig_bio", "people": 1}]', 'a repeat open keeps the first source of the day';
end $$;

select 'growth SQL tests passed' as result;
