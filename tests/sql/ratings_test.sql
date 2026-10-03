-- Behavioural tests for supabase/migrations/*_ratings_profiles.sql.
\set ON_ERROR_STOP on
set client_min_messages = warning;

insert into public.places (id, kind, name, zone, lat, lng, radius_m) values
  ('r_food', 'food', 'Rated Cabin', 'north', 22.5945, 88.3660, 300)
on conflict do nothing;

do $$ declare r jsonb; begin
  perform set_config('request.jwt.claims', '{"sub": "aaaaaaaa-1111-1111-1111-111111111111", "role": "authenticated"}', false);
  set local role authenticated;
  r := public.rate_place('r_food', 5, array['tasty']);
  assert r->>'status' = 'visit_first', 'only people who checked in can rate: ' || r::text;
  r := public.record_visit('r_food', 22.5945, 88.3660, 10);
  assert r->>'status' = 'counted', r::text;
  r := public.rate_place('r_food', 9);
  assert r->>'status' = 'bad_stars', r::text;
  r := public.rate_place('nope', 4);
  assert r->>'status' = 'unknown_place', r::text;
  r := public.rate_place('r_food', 5, array['tasty', 'value', 'tasty', '<script>']);
  assert r->>'status' = 'ok' and (r->>'ratings')::int = 1 and (r->>'rating')::numeric = 5, r::text;
  assert r->'top_tags' @> '["tasty", "value"]' and jsonb_array_length(r->'top_tags') = 2, 'junk and duplicate tags dropped: ' || r::text;
  r := public.rate_place('r_food', 3, array['quick']);                  -- changing your mind overwrites
  assert (r->>'ratings')::int = 1 and (r->>'rating')::numeric = 3, r::text;
end $$;

do $$ declare r jsonb; begin
  perform set_config('request.jwt.claims', '{"sub": "aaaaaaaa-2222-2222-2222-222222222222", "role": "authenticated"}', false);
  set local role authenticated;
  perform public.record_visit('r_food', 22.5946, 88.3661, 10);
  r := public.rate_place('r_food', 4, array['quick', 'value']);
  assert (r->>'ratings')::int = 2 and (r->>'rating')::numeric = 3.5, r::text;
  assert r->'top_tags'->>0 = 'quick', 'most-said tag first: ' || r::text;
end $$;

-- Anyone can read the averages; nobody can read who rated what.
do $$ declare n int; begin
  perform set_config('request.jwt.claims', '', false);
  set local role anon;
  select ratings into n from public.place_rating_stats where place_id = 'r_food';
  assert n = 2, 'stats readable';
  begin perform 1 from public.place_ratings; assert false, 'raw ratings must not be readable';
  exception when insufficient_privilege then null; end;
  begin perform public.rate_place('r_food', 5); assert false, 'anon cannot rate';
  exception when insufficient_privilege then null; end;
end $$;

-- Profiles: saved only with consent, never readable, erased when consent is withdrawn.
do $$ declare r jsonb; begin
  assert public.normalize_in_mobile('098300 12345') = '+919830012345';
  assert public.normalize_in_mobile('+91-98300-12345') = '+919830012345';
  assert public.normalize_in_mobile('12345') is null and public.normalize_in_mobile('5830012345') is null;
  perform set_config('request.jwt.claims', '{"sub": "aaaaaaaa-1111-1111-1111-111111111111", "role": "authenticated"}', false);
  set local role authenticated;
  r := public.save_profile('Rina', '98300 12345', false);
  assert r->>'status' = 'deleted', r::text;
  r := public.save_profile('Rina', '123', true);
  assert r->>'status' = 'bad_phone', r::text;
  r := public.save_profile('  Rina Sen ', '+91 98300 12345', true);
  assert r->>'status' = 'ok', r::text;
  begin perform 1 from public.profiles; assert false, 'profiles must not be readable, even by the owner';
  exception when insufficient_privilege then null; end;
end $$;
do $$ begin
  assert (select name || phone from public.profiles) = 'Rina Sen+919830012345';
  perform set_config('request.jwt.claims', '{"sub": "aaaaaaaa-1111-1111-1111-111111111111", "role": "authenticated"}', false);
  set local role authenticated;
  perform public.save_profile(null, null, false);
  reset role;
  assert not exists (select 1 from public.profiles), 'withdrawing consent erases the row';
end $$;

select 'ratings/profile SQL tests passed' as result;
