-- Behavioural tests for supabase/migrations/*_contacts.sql (the opted-in contacts repository).
\set ON_ERROR_STOP on
set client_min_messages = warning;

do $$ declare r jsonb; begin
  perform set_config('request.jwt.claims', '{"sub": "cccccccc-0000-0000-0000-000000000001", "role": "authenticated"}', false);
  set local role authenticated;
  perform public.record_visit('t_food', 22.5945, 88.3660, 10);
  r := public.save_profile('Tumpa Das', '9830098300', true, 'bn', 'QR_Lake_Town', 'dddddddd-0000-0000-0000-000000000001');
  assert r->>'status' = 'ok', r::text;
  r := public.save_profile('Tumpa', '9830098300', true, 'xx', 'ig_bio', null);   -- an edit: first source and device stay
  assert r->>'status' = 'ok', r::text;
end $$;

do $$ begin
  set local role anon;
  perform track_open('dddddddd-0000-0000-0000-000000000001', 'qr_lake_town', 'qr_lake_town');
end $$;

-- The team's view: one row, the data points joined in; nothing readable from the app.
do $$ declare c record; s jsonb; begin
  select * into c from public.contacts_report();
  assert c.name = 'Tumpa' and c.phone = '+919830098300' and c.lang = 'bn', row_to_json(c)::text;
  assert c.first_src = 'qr_lake_town' and c.days_active = 1 and c.eateries = 1 and c.pandals = 0, row_to_json(c)::text;
  s := public.contacts_summary();
  assert (s->>'contacts')::int = 1 and s->'by_lang'->>'bn' = '1' and s->'by_source'->>'qr_lake_town' = '1', s::text;
  assert (select array_agg(action order by id) from public.consent_log) = array['granted', 'updated'], 'consent log';
end $$;
do $$ begin
  set local role authenticated;
  begin perform * from public.contacts_report(); assert false, 'contacts_report must not be callable from the app';
  exception when insufficient_privilege then null; end;
  begin perform 1 from public.consent_log; assert false, 'consent_log must not be readable';
  exception when insufficient_privilege then null; end;
end $$;

-- Withdrawal deletes the person and is logged without any personal data.
do $$ begin
  perform set_config('request.jwt.claims', '{"sub": "cccccccc-0000-0000-0000-000000000001", "role": "authenticated"}', false);
  set local role authenticated;
  perform public.save_profile(null, null, false);
end $$;
do $$ begin
  assert not exists (select 1 from public.profiles), 'profile erased';
  assert (select action from public.consent_log order by id desc limit 1) = 'withdrawn';
  assert (public.contacts_summary()->>'withdrawn')::int = 1;
end $$;

delete from public.app_opens where device_id = 'dddddddd-0000-0000-0000-000000000001';  -- leave the reach tests' numbers alone

select 'contacts SQL tests passed' as result;
