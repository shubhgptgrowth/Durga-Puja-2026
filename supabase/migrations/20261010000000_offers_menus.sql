-- Eateries: pujo offers posted by the restaurant, and menu photos.
--
-- Offers: an owner or manager fills "Post a pujo offer" on the eatery page (what, valid from/to, their name
-- and phone). It waits as 'pending' until the team calls them back and approves it (offers workflow or the
-- dashboard: analytics.offers_pending). Approved offers show while they are valid. The phone is for that
-- call only: it is never in a public view, a log or an export.
--
-- Menu photos: ordinary uploads to the moments bucket tagged 'menu'. They show under Menu on the eatery
-- page, not in the Moments feed.

-- ---------------------------------------------------------------- menu photos
alter table public.photos add column if not exists tag text check (tag in ('menu'));
create index if not exists photos_menu_idx on public.photos (place_id, created_at desc) where tag = 'menu' and not hidden;

create or replace view public.photos_feed as
  select ph.id, ph.place_id, ph.media_type, ph.path, ph.thumb_path, ph.caption, ph.on_site,
         ph.likes, ph.created_at,
         (ph.user_id = auth.uid()) as mine,
         exists (select 1 from public.photo_likes l where l.photo_id = ph.id and l.user_id = auth.uid()) as liked,
         ph.tag
  from public.photos ph
  where not ph.hidden;
grant select on public.photos_feed to anon, authenticated;

drop function if exists public.add_photo(text, text, text, text, text, double precision, double precision, double precision);
create or replace function public.add_photo(
  p_place text, p_path text, p_thumb_path text, p_media_type text,
  p_caption text default null, p_lat double precision default null,
  p_lng double precision default null, p_accuracy double precision default null,
  p_tag text default null)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_uid   uuid := auth.uid();
  v_place places%rowtype;
  v_dist  double precision;
  v_id    uuid;
  v_on    boolean := false;
begin
  if v_uid is null then
    raise exception 'sign-in required' using errcode = '28000';
  end if;
  select * into v_place from places where id = p_place;
  if not found then
    return jsonb_build_object('status', 'unknown_place');
  end if;
  if p_media_type not in ('image', 'video') then
    return jsonb_build_object('status', 'bad_media');
  end if;
  if p_tag is not null and (p_tag <> 'menu' or v_place.kind <> 'food' or p_media_type <> 'image') then
    return jsonb_build_object('status', 'bad_tag');
  end if;
  if p_path not like v_uid::text || '/%' or p_thumb_path not like v_uid::text || '/%' then
    return jsonb_build_object('status', 'bad_path');
  end if;
  if not exists (select 1 from storage.objects where bucket_id = 'moments' and name = p_path) then
    return jsonb_build_object('status', 'not_uploaded');
  end if;
  if (select count(*) from photos where user_id = v_uid and created_at > now() - interval '24 hours') >= 30
     or (select count(*) from photos where user_id = v_uid and created_at > now() - interval '10 minutes') >= 6 then
    return jsonb_build_object('status', 'rate_limited');
  end if;

  if p_lat is not null and p_lng is not null then
    v_dist := distance_m(p_lat, p_lng, v_place.lat, v_place.lng);
    v_on := v_dist <= v_place.radius_m + least(greatest(coalesce(p_accuracy, 50), 0), 100);
  end if;

  insert into photos (user_id, place_id, media_type, path, thumb_path, caption, on_site, distance_m, tag)
  values (v_uid, p_place, p_media_type, p_path, p_thumb_path,
          nullif(left(btrim(coalesce(p_caption, '')), 140), ''), v_on, round(v_dist), p_tag)
  returning id into v_id;

  if p_tag is null then  -- menus aren't moments
    insert into place_counters (place_id, photos) values (p_place, 1)
      on conflict (place_id) do update set photos = place_counters.photos + 1;
  end if;

  return jsonb_build_object('status', 'ok', 'id', v_id, 'on_site', v_on);
end $$;
revoke all on function public.add_photo(text, text, text, text, text, double precision, double precision, double precision, text) from public, anon;
grant execute on function public.add_photo(text, text, text, text, text, double precision, double precision, double precision, text) to authenticated;

-- ---------------------------------------------------------------- offers
create table if not exists public.food_offers (
  id             uuid primary key default gen_random_uuid(),
  place_id       text not null references public.places (id) on delete cascade,
  title          text not null check (char_length(title) between 3 and 80),
  details        text check (char_length(details) <= 240),
  valid_from     date not null,
  valid_to       date not null,
  contact_name   text not null check (char_length(contact_name) between 2 and 60),
  contact_phone  text not null check (contact_phone ~ '^\+91[6-9][0-9]{9}$'),
  status         text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
  submitted_by   uuid not null,
  created_at     timestamptz not null default now(),
  reviewed_at    timestamptz,
  check (valid_to >= valid_from)
);
create index if not exists food_offers_live on public.food_offers (place_id, valid_to) where status = 'approved';
create index if not exists food_offers_user on public.food_offers (submitted_by, created_at desc);
alter table public.food_offers enable row level security;
revoke all on public.food_offers from anon, authenticated;

-- What diners see: approved offers that haven't ended. No contact details.
-- (Dropped and recreated so re-running this file after *_featured_offers.sql, which adds a column, still works.)
drop view if exists public.offers_feed;
create view public.offers_feed as
  select o.id, o.place_id, o.title, o.details, o.valid_from, o.valid_to
  from public.food_offers o
  where o.status = 'approved' and o.valid_to >= public.ist_today();
grant select on public.offers_feed to anon, authenticated;

create or replace function public.submit_offer(
  p_place text, p_title text, p_details text, p_from date, p_to date, p_name text, p_phone text)
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
  insert into food_offers (place_id, title, details, valid_from, valid_to, contact_name, contact_phone, submitted_by)
  values (p_place, left(btrim(p_title), 80), nullif(left(btrim(coalesce(p_details, '')), 240), ''),
          greatest(p_from, ist_today()), p_to, left(btrim(p_name), 60), '+91' || v_phone, v_uid)
  returning id into v_id;
  return jsonb_build_object('status', 'pending', 'id', v_id);
end $$;
revoke all on function public.submit_offer(text, text, text, date, date, text, text) from public, anon;
grant execute on function public.submit_offer(text, text, text, date, date, text, text) to authenticated;

-- The team's review (offers workflow / SQL editor only; not callable from the app).
create or replace function public.review_offer(p_id uuid, p_status text) returns jsonb
language plpgsql security definer set search_path = public as $$
begin
  if p_status not in ('approved', 'rejected', 'pending') then return jsonb_build_object('status', 'bad_status'); end if;
  update food_offers set status = p_status, reviewed_at = now() where id = p_id;
  if not found then return jsonb_build_object('status', 'not_found'); end if;
  return jsonb_build_object('status', 'ok');
end $$;
revoke all on function public.review_offer(uuid, text) from public, anon, authenticated;

-- For the offers workflow's public summary: no phone numbers, only whether one was given.
create or replace function public.offers_report() returns jsonb
language sql stable security definer set search_path = public as $$
  select coalesce(jsonb_agg(jsonb_build_object(
    'id', o.id, 'place_id', o.place_id, 'place', p.name, 'title', o.title, 'details', o.details,
    'valid_from', o.valid_from, 'valid_to', o.valid_to, 'status', o.status, 'created_at', o.created_at)
    order by (o.status = 'pending') desc, o.created_at desc), '[]')
  from food_offers o join places p on p.id = o.place_id
  where o.status = 'pending' or o.valid_to >= ist_today()
$$;
revoke all on function public.offers_report() from public, anon, authenticated;

-- In the dashboard (Table editor → schema "analytics"): offers waiting for a call back, with the number to call.
drop view if exists analytics.offers_pending;
create view analytics.offers_pending as
  select o.id, p.name as place, o.title, o.details, o.valid_from, o.valid_to, o.contact_name, o.contact_phone, o.created_at
  from public.food_offers o join public.places p on p.id = o.place_id
  where o.status = 'pending' order by o.created_at;
revoke all on analytics.offers_pending from anon, authenticated;
