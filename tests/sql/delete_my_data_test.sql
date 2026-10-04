-- Behavioural tests for supabase/migrations/*_delete_my_data.sql.
\set ON_ERROR_STOP on
set client_min_messages = warning;

insert into storage.objects (bucket_id, name) values
  ('moments', 'efefefef-0000-0000-0000-000000000001/d.jpg'), ('moments', 'efefefef-0000-0000-0000-000000000001/d_t.jpg');

do $$ declare r jsonb; begin
  perform set_config('request.jwt.claims', '{"sub": "efefefef-0000-0000-0000-000000000001", "role": "authenticated"}', false);
  set local role authenticated;
  perform public.save_progress('{"history": {"2026-10-18": {"steps": 4000}}}');
  perform public.save_profile('Mou', '9830098300', true);
  perform public.submit_offer('mitra_cafe', 'Free tea', null, public.ist_today(), public.ist_today() + 2, 'Mou', '9830098300');
  r := public.add_photo('t_pandal', 'efefefef-0000-0000-0000-000000000001/d.jpg', 'efefefef-0000-0000-0000-000000000001/d_t.jpg', 'image');
  assert r->>'status' = 'ok', r::text;
  r := public.delete_my_data();
  assert r->>'status' = 'ok' and jsonb_array_length(r->'files') = 2, r::text;
  assert public.load_progress() is null, 'backup gone';
end $$;

do $$ declare u uuid := 'efefefef-0000-0000-0000-000000000001'; begin
  assert not exists (select 1 from public.progress_members where user_id = u);
  assert not exists (select 1 from public.profiles where user_id = u);
  assert not exists (select 1 from public.food_offers where submitted_by = u);
  assert not exists (select 1 from public.photos where user_id = u);
  assert (select action from public.consent_log where user_id = u order by at desc, id desc limit 1) = 'withdrawn';
end $$;

select 'delete_my_data ok';
