-- Behavioural tests for supabase/migrations/*_offers_menus.sql (restaurant offers and menu photos).
\set ON_ERROR_STOP on
set client_min_messages = warning;

insert into storage.objects (bucket_id, name) values
  ('moments', 'cdcdcdcd-0000-0000-0000-000000000001/menu.jpg'),
  ('moments', 'cdcdcdcd-0000-0000-0000-000000000001/menu_t.jpg');

do $$ declare r jsonb; before int; begin
  perform set_config('request.jwt.claims', '{"sub": "cdcdcdcd-0000-0000-0000-000000000001", "role": "authenticated"}', false);
  set local role authenticated;
  before := coalesce((select photos from public.place_stats where place_id = 'mitra_cafe'), 0);
  r := public.add_photo('bagbazar', 'cdcdcdcd-0000-0000-0000-000000000001/menu.jpg', 'cdcdcdcd-0000-0000-0000-000000000001/menu_t.jpg', 'image', null, null, null, null, 'menu');
  assert r->>'status' = 'bad_tag', 'menus only for eateries: ' || r::text;
  r := public.add_photo('mitra_cafe', 'cdcdcdcd-0000-0000-0000-000000000001/menu.jpg', 'cdcdcdcd-0000-0000-0000-000000000001/menu_t.jpg', 'image', 'Pujo menu', null, null, null, 'menu');
  assert r->>'status' = 'ok', r::text;
  assert (select tag from public.photos_feed where id = (r->>'id')::uuid) = 'menu';
  assert coalesce((select photos from public.place_stats where place_id = 'mitra_cafe'), 0) = before, 'menus are not counted as moments';

  -- Offers
  r := public.submit_offer('bagbazar', '10% off', null, public.ist_today(), public.ist_today() + 5, 'Ratan', '9830012345');
  assert r->>'status' = 'unknown_place', 'offers only for eateries';
  r := public.submit_offer('mitra_cafe', '10% off', null, public.ist_today(), public.ist_today() + 5, 'Ratan', '12345');
  assert r->>'status' = 'bad_phone', r::text;
  r := public.submit_offer('mitra_cafe', '10% off', null, public.ist_today(), public.ist_today() - 1, 'Ratan', '9830012345');
  assert r->>'status' = 'bad_dates', r::text;
  r := public.submit_offer('mitra_cafe', '  Free mishti doi with every thali  ', 'Saptami to Dashami, dine-in', public.ist_today(), public.ist_today() + 5, 'Ratan Mitra', '+91 98300 12345');
  assert r->>'status' = 'pending', r::text;
  perform set_config('pp.offer', r->>'id', false);
  assert not exists (select 1 from public.offers_feed), 'pending offers are not shown';
  begin perform 1 from public.food_offers; assert false, 'offers table must not be readable';
  exception when insufficient_privilege then null; end;
  begin perform public.review_offer((r->>'id')::uuid, 'approved'); assert false, 'the app cannot approve';
  exception when insufficient_privilege then null; end;
end $$;

-- The team approves; diners see it, without contact details.
do $$ declare r jsonb; f record; begin
  r := public.review_offer(current_setting('pp.offer')::uuid, 'approved');
  assert r->>'status' = 'ok', r::text;
  assert (select contact_phone from public.food_offers where id = current_setting('pp.offer')::uuid) = '+919830012345';
  assert (select count(*) from jsonb_array_elements(public.offers_report()) e where e ? 'contact_phone') = 0, 'no phones in the report';
  set local role anon;
  select * into f from public.offers_feed where place_id = 'mitra_cafe';
  assert f.title = 'Free mishti doi with every thali', f::text;
  assert not exists (select 1 from information_schema.columns where table_name = 'offers_feed' and column_name like 'contact%');
end $$;

-- Rate limit: five a day per person.
do $$ declare r jsonb; begin
  perform set_config('request.jwt.claims', '{"sub": "cdcdcdcd-0000-0000-0000-000000000001", "role": "authenticated"}', false);
  set local role authenticated;
  for i in 1..4 loop perform public.submit_offer('mitra_cafe', 'Offer ' || i, null, public.ist_today(), public.ist_today() + 1, 'Ratan', '9830012345'); end loop;
  r := public.submit_offer('mitra_cafe', 'One too many', null, public.ist_today(), public.ist_today() + 1, 'Ratan', '9830012345');
  assert r->>'status' = 'rate_limited', r::text;
end $$;

select 'offers ok';
