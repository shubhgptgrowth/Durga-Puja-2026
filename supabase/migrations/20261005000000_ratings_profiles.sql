-- Ratings for eateries (and pandals), and an optional contact profile.
--
-- Ratings: one per person per place, 1–5 stars plus up to three quick tags. Only people who
-- checked in at the place (a GPS-verified visit, see record_visit) can rate it, so every star
-- comes from someone who was actually there. Changing your mind overwrites your rating.
--
-- Profiles: a name and phone number, saved only when the person ticks the consent box in
-- My Pujo (the app keeps them on the phone otherwise). Nobody can read them through the API,
-- not even the owner; delete_profile() erases the row. Purpose: pujo updates from the team.

-- ---------------------------------------------------------------- ratings
create table if not exists public.place_ratings (
  place_id    text not null references public.places (id) on delete cascade,
  user_id     uuid not null,
  stars       smallint not null check (stars between 1 and 5),
  tags        text[] not null default '{}',
  updated_at  timestamptz not null default now(),
  primary key (place_id, user_id)
);
alter table public.place_ratings enable row level security;
revoke all on public.place_ratings from anon, authenticated;

create or replace function public.rating_tags() returns text[] language sql immutable as $$
  select array['tasty', 'value', 'quick', 'clean', 'friendly', 'crowded', 'pricey', 'slow']
$$;

create or replace view public.place_rating_stats as
  select r.place_id,
         round(avg(r.stars)::numeric, 1) as rating,
         count(*)::integer as ratings,
         coalesce((select array_agg(t order by n desc, t) from (
             select t, count(*) as n from public.place_ratings r2, unnest(r2.tags) t
             where r2.place_id = r.place_id group by t order by n desc, t limit 3) top), '{}') as top_tags
  from public.place_ratings r
  group by r.place_id;
grant select on public.place_rating_stats to anon, authenticated;

create or replace function public.rate_place(p_place text, p_stars integer, p_tags text[] default '{}')
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_uid  uuid := auth.uid();
  v_tags text[];
  s      record;
begin
  if v_uid is null then
    raise exception 'sign-in required' using errcode = '28000';
  end if;
  if not exists (select 1 from places where id = p_place) then
    return jsonb_build_object('status', 'unknown_place');
  end if;
  if p_stars is null or p_stars not between 1 and 5 then
    return jsonb_build_object('status', 'bad_stars');
  end if;
  if not exists (select 1 from visits where user_id = v_uid and place_id = p_place) then
    return jsonb_build_object('status', 'visit_first');
  end if;
  select coalesce(array_agg(distinct t), '{}') into v_tags
    from unnest(coalesce(p_tags, '{}')) t where t = any (rating_tags());
  v_tags := v_tags[1:3];
  insert into place_ratings (place_id, user_id, stars, tags) values (p_place, v_uid, p_stars, v_tags)
  on conflict (place_id, user_id) do update set stars = excluded.stars, tags = excluded.tags, updated_at = now();
  select * into s from place_rating_stats where place_id = p_place;
  return jsonb_build_object('status', 'ok', 'rating', s.rating, 'ratings', s.ratings, 'top_tags', to_jsonb(s.top_tags));
end $$;
revoke all on function public.rate_place(text, integer, text[]) from public, anon;
grant execute on function public.rate_place(text, integer, text[]) to authenticated;

-- ---------------------------------------------------------------- profiles (opt-in contact)
create table if not exists public.profiles (
  user_id     uuid primary key,
  name        text check (char_length(name) <= 60),
  phone       text check (phone ~ '^\+91[6-9][0-9]{9}$'),
  consent_at  timestamptz not null,
  updated_at  timestamptz not null default now()
);
alter table public.profiles enable row level security;
revoke all on public.profiles from anon, authenticated;

-- Indian mobile numbers only: accepts "98300 12345", "+91-9830012345", "09830012345".
create or replace function public.normalize_in_mobile(p text) returns text language sql immutable as $$
  select case when d ~ '^[6-9][0-9]{9}$' then '+91' || d end
  from (select regexp_replace(regexp_replace(coalesce(p, ''), '[^0-9]', '', 'g'), '^(91|0)(?=[6-9][0-9]{9}$)', '') as d) x
$$;

create or replace function public.save_profile(p_name text, p_phone text, p_consent boolean)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_uid   uuid := auth.uid();
  v_phone text := normalize_in_mobile(p_phone);
  v_name  text := nullif(left(btrim(coalesce(p_name, '')), 60), '');
begin
  if v_uid is null then
    raise exception 'sign-in required' using errcode = '28000';
  end if;
  if not coalesce(p_consent, false) then
    delete from profiles where user_id = v_uid;
    return jsonb_build_object('status', 'deleted');
  end if;
  if v_phone is null then
    return jsonb_build_object('status', 'bad_phone');
  end if;
  insert into profiles (user_id, name, phone, consent_at) values (v_uid, v_name, v_phone, now())
  on conflict (user_id) do update set name = excluded.name, phone = excluded.phone, updated_at = now();
  return jsonb_build_object('status', 'ok');
end $$;
revoke all on function public.save_profile(text, text, boolean) from public, anon;
grant execute on function public.save_profile(text, text, boolean) to authenticated;
