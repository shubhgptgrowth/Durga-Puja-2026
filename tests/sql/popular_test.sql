-- Behavioural tests for supabase/migrations/*_place_popular.sql ("most opened this week" on Home).
\set ON_ERROR_STOP on
set client_min_messages = warning;

do $$ declare n int; r record; begin
  -- 6 people open pop_a, 4 open pop_b (under the floor of 5), and one person opens pop_a three times.
  for i in 1..6 loop
    perform public.track(('cccccccc-0000-0000-0000-00000000000' || i)::uuid,
      '[{"n": "place_open", "view": "explore", "place": "pop_a", "kind": "pandal"}]');
  end loop;
  perform public.track('cccccccc-0000-0000-0000-000000000001',
    '[{"n": "place_open", "view": "explore", "place": "pop_a", "kind": "pandal"}, {"n": "place_open", "view": "explore", "place": "pop_a", "kind": "pandal"}]');
  for i in 1..4 loop
    perform public.track(('cccccccc-0000-0000-0000-00000000001' || i)::uuid,
      '[{"n": "place_open", "view": "explore", "place": "pop_b", "kind": "pandal"}]');
  end loop;
  -- A parking spot opened by 6 people is not a pandal, and an old open does not count.
  for i in 1..6 loop
    perform public.track(('cccccccc-0000-0000-0000-00000000002' || i)::uuid,
      '[{"n": "place_open", "view": "explore", "place": "pop_park", "kind": "parking"}]');
  end loop;
  insert into public.events (device_id, at, day, name, place_id, kind)
    select ('cccccccc-0000-0000-0000-00000000003' || i)::uuid, now() - interval '9 days', public.ist_today() - 9, 'place_open', 'pop_old', 'pandal'
    from generate_series(1, 6) i;

  set local role anon;
  select * into r from public.place_popular where place_id = 'pop_a';
  assert r.people_7d = 6, 'people, not opens: ' || coalesce(r.people_7d::text, 'missing');
  select count(*) into n from public.place_popular where place_id in ('pop_b', 'pop_park', 'pop_old');
  assert n = 0, 'under 5 people, parking and older than a week are left out';
  begin perform device_id from public.place_popular; assert false, 'no device ids';
  exception when undefined_column then null; end;
end $$;
select 'popular ok';
