-- Behavioural tests for supabase/migrations/*_community.sql. Any failed assertion aborts with an error.
\set ON_ERROR_STOP on
set client_min_messages = warning;

create or replace function pg_temp.as_user(u text) returns void language sql as $$
  select set_config('request.jwt.claims', json_build_object('sub', u, 'role', 'authenticated')::text, false);
$$;

-- Fixture places, independent of the real data: a pandal at 22.5185, 88.3489 (350 m radius) and an eatery.
insert into public.places (id, kind, name, zone, lat, lng, radius_m) values
  ('t_pandal', 'pandal', 'Test Pandal', 'south_lakemarket', 22.5185, 88.3489, 350),
  ('t_food', 'food', 'Test Cabin', 'north', 22.5945, 88.3660, 350);

do $$ declare r jsonb; begin
  perform pg_temp.as_user('11111111-1111-1111-1111-111111111111');
  set local role authenticated;

  r := public.record_visit('t_pandal', 22.5185, 88.3489, 10);
  assert r->>'status' = 'counted', r::text;
  assert (r->>'today')::int = 1 and (r->>'visits')::int = 1, r::text;

  r := public.record_visit('t_pandal', 22.5186, 88.3490, 10);
  assert r->>'status' = 'duplicate', 'same person, same day: counted once';

  r := public.record_visit('t_pandal', 22.5726, 88.3639, 10);          -- from College Street
  assert r->>'status' = 'too_far' and (r->>'distance_m')::int > 5000, r::text;

  r := public.record_visit('t_pandal', 22.5185, 88.3489, 10, now() - interval '13 hours');
  assert r->>'status' = 'expired', r::text;

  r := public.record_visit('nowhere', 22.5185, 88.3489, 10);
  assert r->>'status' = 'unknown_place', r::text;

  r := public.record_visit('t_food', 22.5945, 88.3660, 15);         -- food → "ate"
  assert r->>'status' = 'counted', r::text;
end $$;

-- A second person raises the counts; the stats view aggregates without exposing anyone.
do $$ declare r jsonb; s record; begin
  perform pg_temp.as_user('22222222-2222-2222-2222-222222222222');
  set local role authenticated;
  r := public.record_visit('t_pandal', 22.5190, 88.3480, 30);
  assert r->>'status' = 'counted' and (r->>'today')::int = 2, r::text;
  select * into s from public.place_stats where place_id = 't_pandal';
  assert s.visits = 2 and s.today = 2 and s.last_hour = 2, s::text;
  select * into s from public.place_stats where place_id = 't_food';
  assert s.visits = 1 and s.kind = 'food', s::text;
end $$;

-- Tables are not directly readable or writable by clients.
do $$ begin
  perform pg_temp.as_user('22222222-2222-2222-2222-222222222222');
  set local role authenticated;
  begin
    perform 1 from public.visits limit 1;
    assert false, 'visits must not be selectable';
  exception when insufficient_privilege then null; end;
  begin
    insert into public.visits (user_id, place_id, kind, day) values (auth.uid(), 't_pandal', 'checkin', current_date + 1);
    assert false, 'visits must not be insertable';
  exception when insufficient_privilege then null; end;
end $$;

-- Anonymous (signed-out) callers can read stats but cannot record visits.
do $$ begin
  perform set_config('request.jwt.claims', '', false);
  set local role anon;
  perform 1 from public.place_stats limit 1;
  begin
    perform public.record_visit('t_pandal', 22.5185, 88.3489, 10);
    assert false, 'anon must not execute record_visit';
  exception when insufficient_privilege then null; end;
end $$;

-- Rate limit: 40 visits an hour per person.
do $$ declare r jsonb; i int; begin
  for i in 1..41 loop
    insert into public.places (id, kind, name, zone, lat, lng) values ('rl_' || i, 'pandal', 'RL ' || i, 'north', 22.6, 88.36)
      on conflict do nothing;
  end loop;
  perform pg_temp.as_user('33333333-3333-3333-3333-333333333333');
  set local role authenticated;
  for i in 1..40 loop
    r := public.record_visit('rl_' || i, 22.6, 88.36, 5);
    assert r->>'status' = 'counted', r::text;
  end loop;
  r := public.record_visit('rl_41', 22.6, 88.36, 5);
  assert r->>'status' = 'rate_limited', r::text;
end $$;

-- Photos: must be uploaded into your own folder first; on-site is computed server-side.
insert into storage.objects (bucket_id, name) values
  ('moments', '11111111-1111-1111-1111-111111111111/a.jpg'),
  ('moments', '11111111-1111-1111-1111-111111111111/a_t.jpg'),
  ('moments', '22222222-2222-2222-2222-222222222222/b.jpg');

do $$ declare r jsonb; pid uuid; f record; begin
  perform pg_temp.as_user('11111111-1111-1111-1111-111111111111');
  set local role authenticated;

  r := public.add_photo('t_pandal', '22222222-2222-2222-2222-222222222222/b.jpg', '22222222-2222-2222-2222-222222222222/b.jpg', 'image');
  assert r->>'status' = 'bad_path', 'cannot register someone else''s file';

  r := public.add_photo('t_pandal', '11111111-1111-1111-1111-111111111111/missing.jpg', '11111111-1111-1111-1111-111111111111/missing.jpg', 'image');
  assert r->>'status' = 'not_uploaded', r::text;

  r := public.add_photo('t_pandal', '11111111-1111-1111-1111-111111111111/a.jpg', '11111111-1111-1111-1111-111111111111/a_t.jpg',
                        'image', '  Dazzling lights!  ', 22.5186, 88.3488, 12);
  assert r->>'status' = 'ok' and (r->>'on_site')::boolean, r::text;
  pid := (r->>'id')::uuid;

  select * into f from public.photos_feed where id = pid;
  assert f.caption = 'Dazzling lights!' and f.mine and not f.liked, f::text;
  assert (select photos from public.place_stats where place_id = 't_pandal') = 1;

  r := public.toggle_like(pid);
  assert (r->>'liked')::boolean and (r->>'likes')::int = 1, r::text;
  r := public.toggle_like(pid);
  assert not (r->>'liked')::boolean and (r->>'likes')::int = 0, r::text;
  perform set_config('pp.photo', pid::text, false);
end $$;

-- Three distinct reports hide a photo and decrement the count; repeat reports are ignored.
do $$ declare r jsonb; pid uuid := current_setting('pp.photo')::uuid; u text; begin
  foreach u in array array['22222222-2222-2222-2222-222222222222', '22222222-2222-2222-2222-222222222222',
                           '33333333-3333-3333-3333-333333333333', '44444444-4444-4444-4444-444444444444'] loop
    perform pg_temp.as_user(u);
    set local role authenticated;
    r := public.report_photo(pid, 'spam');
  end loop;
  assert not exists (select 1 from public.photos_feed where id = pid), 'reported photo should be hidden';
  assert (select photos from public.place_stats where place_id = 't_pandal') = 0;
end $$;

-- Only the owner can delete; delete returns the storage paths to remove.
do $$ declare r jsonb; pid uuid := current_setting('pp.photo')::uuid; begin
  perform pg_temp.as_user('22222222-2222-2222-2222-222222222222');
  set local role authenticated;
  r := public.delete_photo(pid);
  assert r->>'status' = 'not_found', 'non-owner cannot delete';
  perform pg_temp.as_user('11111111-1111-1111-1111-111111111111');
  r := public.delete_photo(pid);
  assert r->>'status' = 'ok' and r->>'path' like '11111111-%', r::text;
end $$;

-- Storage policy: you may only upload into your own folder.
do $$ begin
  assert (storage.foldername('11111111-1111-1111-1111-111111111111/x/y.jpg'))[1] = '11111111-1111-1111-1111-111111111111';
end $$;

select 'community SQL tests passed' as result;
