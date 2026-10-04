-- Behavioural tests for supabase/migrations/*_progress_sync.sql (My Pujo across browsers).
\set ON_ERROR_STOP on
set client_min_messages = warning;

do $$ declare r jsonb; code text; begin
  perform set_config('request.jwt.claims', '{"sub": "abababab-0000-0000-0000-000000000001", "role": "authenticated"}', false);
  set local role authenticated;
  assert public.load_progress() is null, 'nothing saved yet';
  r := public.save_progress('{"history": {"2026-10-18": {"steps": 5000}}}');
  assert r->>'status' = 'ok' and r->>'code' ~ '^PUJO-[A-Z2-9]{4}-[A-Z2-9]{4}$', r::text;
  code := r->>'code';
  r := public.save_progress('{"history": {"2026-10-18": {"steps": 6000}}}');
  assert r->>'code' = code, 'same code on later saves';
  assert (public.load_progress()->'data'->'history'->'2026-10-18'->>'steps')::int = 6000;
  assert public.save_progress('"x"')->>'status' = 'bad_data';
  perform set_config('pp.code', code, false);
end $$;

-- A second browser: its own small backup, then it joins the first one's code (typed in lower case, no dashes).
do $$ declare r jsonb; code text := current_setting('pp.code'); begin
  perform set_config('request.jwt.claims', '{"sub": "abababab-0000-0000-0000-000000000002", "role": "authenticated"}', false);
  set local role authenticated;
  perform public.save_progress('{"history": {}}');
  r := public.claim_progress('nope');
  assert r->>'status' = 'not_found', r::text;
  r := public.claim_progress(lower(replace(replace(code, 'PUJO-', ''), '-', '')));
  assert r->>'status' = 'ok' and r->>'code' = code and (r->'data'->'history'->'2026-10-18'->>'steps')::int = 6000, r::text;
  r := public.save_progress('{"history": {"2026-10-18": {"steps": 6000}, "2026-10-19": {"steps": 900}}}');
  assert r->>'code' = code, 'saves now go to the shared code';
end $$;

do $$ begin
  assert (select count(*) from public.progress) = 1, 'the second browser''s own backup was folded in and dropped';
  assert (select count(*) from public.progress_members m where m.code = current_setting('pp.code')) = 2;
  perform set_config('request.jwt.claims', '{"sub": "abababab-0000-0000-0000-000000000001", "role": "authenticated"}', false);
  set local role authenticated;
  assert (public.load_progress()->'data'->'history'->'2026-10-19'->>'steps')::int = 900, 'the first browser sees the second''s steps';
  begin perform 1 from public.progress; assert false, 'progress must not be readable directly';
  exception when insufficient_privilege then null; end;
end $$;

-- Guessing codes is rate limited.
do $$ declare r jsonb; begin
  perform set_config('request.jwt.claims', '{"sub": "abababab-0000-0000-0000-000000000003", "role": "authenticated"}', false);
  set local role authenticated;
  for i in 1..10 loop perform public.claim_progress('PUJO-AAAA-AAAA'); end loop;
  r := public.claim_progress('PUJO-AAAA-AAAA');
  assert r->>'status' = 'rate_limited', r::text;
end $$;

select 'progress SQL tests passed' as result;
