-- Featured (paid) eatery offers: Phase 0 of docs/product/BUSINESS_ROADMAP.md.
--
-- An eatery can ask for its pujo offer to be featured (a tick on the offer form). The team calls back as
-- before, takes the payment, then features the offer until a date (offers workflow, action "feature").
-- A featured offer shows as "Sponsored" and its eatery is listed first in Food nearby and the food list.
-- Featuring never touches crowd estimates, routes or pandal order.
-- The payment note (amount, UPI reference) is team-only, like the phone number.

alter table public.food_offers add column if not exists wants_featured boolean not null default false;
alter table public.food_offers add column if not exists featured_until date;
alter table public.food_offers add column if not exists featured_note text check (char_length(featured_note) <= 200);

-- What diners see: approved offers that haven't ended, and whether each is featured today. No contact or payment details.
create or replace view public.offers_feed as
  select o.id, o.place_id, o.title, o.details, o.valid_from, o.valid_to,
         coalesce(o.featured_until >= public.ist_today(), false) as featured
  from public.food_offers o
  where o.status = 'approved' and o.valid_to >= public.ist_today();
grant select on public.offers_feed to anon, authenticated;

-- The form now carries "feature this offer"; the old 7-argument version is replaced (one signature, so
-- PostgREST never has to choose between overloads).
drop function if exists public.submit_offer(text, text, text, date, date, text, text);
create or replace function public.submit_offer(
  p_place text, p_title text, p_details text, p_from date, p_to date, p_name text, p_phone text,
  p_featured boolean default false)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_uid   uuid := auth.uid();
  v_phone text := regexp_replace(coalesce(p_phone, ''), '\D', '', 'g');
  v_id    uuid;
begin
  if v_uid is null then raise exception 'sign-in required' using errcode = '28000'; end if;
  if not exists (select 1 from places where id = p_place and kind = 'food') then
    return jsonb_build_object('status', 'unknown_place');
  end if;
  v_phone := regexp_replace(v_phone, '^(91|0)(?=[6-9][0-9]{9}$)', '');
  if v_phone !~ '^[6-9][0-9]{9}$' then return jsonb_build_object('status', 'bad_phone'); end if;
  if char_length(btrim(coalesce(p_title, ''))) < 3 then return jsonb_build_object('status', 'bad_title'); end if;
  if char_length(btrim(coalesce(p_name, ''))) < 2 then return jsonb_build_object('status', 'bad_name'); end if;
  if p_from is null or p_to is null or p_to < p_from or p_to < ist_today() or p_to > ist_today() + 60 then
    return jsonb_build_object('status', 'bad_dates');
  end if;
  if (select count(*) from food_offers where submitted_by = v_uid and created_at > now() - interval '24 hours') >= 5 then
    return jsonb_build_object('status', 'rate_limited');
  end if;
  insert into food_offers (place_id, title, details, valid_from, valid_to, contact_name, contact_phone, submitted_by, wants_featured)
  values (p_place, left(btrim(p_title), 80), nullif(left(btrim(coalesce(p_details, '')), 240), ''),
          greatest(p_from, ist_today()), p_to, left(btrim(p_name), 60), '+91' || v_phone, v_uid, coalesce(p_featured, false))
  returning id into v_id;
  return jsonb_build_object('status', 'pending', 'id', v_id);
end $$;
revoke all on function public.submit_offer(text, text, text, date, date, text, text, boolean) from public, anon;
grant execute on function public.submit_offer(text, text, text, date, date, text, text, boolean) to authenticated;

-- The team features an offer after payment (offers workflow / SQL editor; not callable from the app).
-- Featuring approves the offer too, and never runs past the offer's own end date. p_until null un-features it.
create or replace function public.feature_offer(p_id uuid, p_until date, p_note text default null) returns jsonb
language plpgsql security definer set search_path = public as $$
declare v_to date;
begin
  select valid_to into v_to from food_offers where id = p_id;
  if not found then return jsonb_build_object('status', 'not_found'); end if;
  if p_until is null then
    update food_offers set featured_until = null where id = p_id;
    return jsonb_build_object('status', 'ok', 'featured_until', null);
  end if;
  if p_until < ist_today() then return jsonb_build_object('status', 'bad_date'); end if;
  update food_offers
     set status = 'approved', reviewed_at = coalesce(reviewed_at, now()),
         featured_until = least(p_until, v_to),
         featured_note = coalesce(nullif(left(btrim(coalesce(p_note, '')), 200), ''), featured_note)
   where id = p_id;
  return jsonb_build_object('status', 'ok', 'featured_until', least(p_until, v_to));
end $$;
revoke all on function public.feature_offer(uuid, date, text) from public, anon, authenticated;

-- The workflow's public summary: still no phone numbers, and no payment notes.
create or replace function public.offers_report() returns jsonb
language sql stable security definer set search_path = public as $$
  select coalesce(jsonb_agg(jsonb_build_object(
    'id', o.id, 'place_id', o.place_id, 'place', p.name, 'title', o.title, 'details', o.details,
    'valid_from', o.valid_from, 'valid_to', o.valid_to, 'status', o.status, 'created_at', o.created_at,
    'wants_featured', o.wants_featured, 'featured_until', o.featured_until)
    order by (o.status = 'pending') desc, o.wants_featured desc, o.created_at desc), '[]')
  from food_offers o join places p on p.id = o.place_id
  where o.status = 'pending' or o.valid_to >= ist_today()
$$;
revoke all on function public.offers_report() from public, anon, authenticated;

-- Dashboard (schema "analytics"): who asked to be featured is on the call list; paid features with their notes.
drop view if exists analytics.offers_pending;   -- a new column in the middle: recreate rather than replace
create view analytics.offers_pending as
  select o.id, p.name as place, o.title, o.details, o.valid_from, o.valid_to, o.contact_name, o.contact_phone,
         o.wants_featured, o.created_at
  from public.food_offers o join public.places p on p.id = o.place_id
  where o.status = 'pending' order by o.wants_featured desc, o.created_at;
revoke all on analytics.offers_pending from anon, authenticated;

create or replace view analytics.offers_featured as
  select o.id, p.name as place, o.title, o.featured_until, o.featured_note, o.contact_name, o.contact_phone, o.reviewed_at
  from public.food_offers o join public.places p on p.id = o.place_id
  where o.featured_until is not null order by o.featured_until desc;
revoke all on analytics.offers_featured from anon, authenticated;
