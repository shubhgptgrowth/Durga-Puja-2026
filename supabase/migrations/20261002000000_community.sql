-- Pujo Parikrama community layer: verified check-ins, "I ate here", and location-tagged moments.
--
-- Design:
--  * Clients never touch the tables directly. RLS is on with no policies, so the
--    only writes go through SECURITY DEFINER RPCs that validate everything.
--  * A visit only counts when the phone is physically near the place: the GPS
--    distance must be within radius_m plus the reported accuracy. Raw coordinates
--    are used for that check and never stored.
--  * Each person counts once per place per day (Asia/Kolkata). People are Supabase
--    anonymous users: no sign-up, but each device gets a stable, rate-limitable identity.
--  * Read paths (place_stats, photos_feed) hit small counter tables, so thousands
--    of phones polling every minute stays cheap.

-- ---------------------------------------------------------------- places
create table if not exists public.places (
  id        text primary key,
  kind      text not null check (kind in ('pandal', 'food')),
  name      text not null,
  zone      text not null,
  lat       double precision not null,
  lng       double precision not null,
  radius_m  integer not null default 300 check (radius_m between 50 and 1000)
);

create or replace function public.distance_m(lat1 double precision, lng1 double precision, lat2 double precision, lng2 double precision)
returns double precision language sql immutable parallel safe as $$
  select 2 * 6371000 * asin(sqrt(
    power(sin(radians(lat2 - lat1) / 2), 2) +
    cos(radians(lat1)) * cos(radians(lat2)) * power(sin(radians(lng2 - lng1) / 2), 2)))
$$;

create or replace function public.ist_today() returns date language sql stable as $$
  select (now() at time zone 'Asia/Kolkata')::date
$$;

-- ---------------------------------------------------------------- visits
create table if not exists public.visits (
  id          bigint generated always as identity primary key,
  user_id     uuid not null,
  place_id    text not null references public.places (id) on delete cascade,
  kind        text not null check (kind in ('checkin', 'ate')),
  day         date not null,
  visited_at  timestamptz not null default now(),
  distance_m  integer,
  unique (user_id, place_id, day)
);
create index if not exists visits_user_recent on public.visits (user_id, visited_at desc);

-- Counters, so reads stay O(places) rather than O(visits).
create table if not exists public.place_counters (
  place_id  text primary key references public.places (id) on delete cascade,
  visits    integer not null default 0,
  photos    integer not null default 0
);
create table if not exists public.place_day_counts (
  place_id  text not null references public.places (id) on delete cascade,
  day       date not null,
  n         integer not null default 0,
  primary key (place_id, day)
);
create table if not exists public.place_bucket_counts (  -- 10-minute buckets, used for "last hour"
  place_id  text not null references public.places (id) on delete cascade,
  bucket    timestamptz not null,
  n         integer not null default 0,
  primary key (place_id, bucket)
);

-- ---------------------------------------------------------------- photos & videos
create table if not exists public.photos (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null,
  place_id    text not null references public.places (id) on delete cascade,
  media_type  text not null check (media_type in ('image', 'video')),
  path        text not null,
  thumb_path  text not null,
  caption     text check (char_length(caption) <= 140),
  on_site     boolean not null default false,
  distance_m  integer,
  likes       integer not null default 0,
  reports     integer not null default 0,
  hidden      boolean not null default false,
  created_at  timestamptz not null default now()
);
create index if not exists photos_feed_idx on public.photos (created_at desc) where not hidden;
create index if not exists photos_place_idx on public.photos (place_id, created_at desc) where not hidden;
create index if not exists photos_user_idx on public.photos (user_id, created_at desc);

create table if not exists public.photo_likes (
  photo_id  uuid not null references public.photos (id) on delete cascade,
  user_id   uuid not null,
  primary key (photo_id, user_id)
);
create table if not exists public.photo_reports (
  photo_id  uuid not null references public.photos (id) on delete cascade,
  user_id   uuid not null,
  reason    text check (char_length(reason) <= 60),
  created_at timestamptz not null default now(),
  primary key (photo_id, user_id)
);

-- Lock every table down. All access goes through the views and functions below.
alter table public.places              enable row level security;
alter table public.visits              enable row level security;
alter table public.place_counters      enable row level security;
alter table public.place_day_counts    enable row level security;
alter table public.place_bucket_counts enable row level security;
alter table public.photos              enable row level security;
alter table public.photo_likes         enable row level security;
alter table public.photo_reports       enable row level security;
revoke all on public.places, public.visits, public.place_counters, public.place_day_counts,
  public.place_bucket_counts, public.photos, public.photo_likes, public.photo_reports from anon, authenticated;

-- ---------------------------------------------------------------- read models
create or replace view public.place_stats as
  select p.id as place_id,
         p.kind,
         coalesce(c.visits, 0) as visits,
         coalesce(d.n, 0) as today,
         coalesce((select sum(b.n) from public.place_bucket_counts b
                   where b.place_id = p.id and b.bucket > now() - interval '1 hour'), 0)::integer as last_hour,
         coalesce(c.photos, 0) as photos
  from public.places p
  left join public.place_counters c on c.place_id = p.id
  left join public.place_day_counts d on d.place_id = p.id and d.day = public.ist_today();

create or replace view public.photos_feed as
  select ph.id, ph.place_id, ph.media_type, ph.path, ph.thumb_path, ph.caption, ph.on_site,
         ph.likes, ph.created_at,
         (ph.user_id = auth.uid()) as mine,
         exists (select 1 from public.photo_likes l where l.photo_id = ph.id and l.user_id = auth.uid()) as liked
  from public.photos ph
  where not ph.hidden;

grant select on public.place_stats, public.photos_feed to anon, authenticated;

-- ---------------------------------------------------------------- helpers
create or replace function public._bump_counts(p_place text, p_at timestamptz) returns void
language sql security definer set search_path = public as $$
  insert into place_counters (place_id, visits) values (p_place, 1)
    on conflict (place_id) do update set visits = place_counters.visits + 1;
  insert into place_day_counts (place_id, day, n) values (p_place, (p_at at time zone 'Asia/Kolkata')::date, 1)
    on conflict (place_id, day) do update set n = place_day_counts.n + 1;
  insert into place_bucket_counts (place_id, bucket, n)
    values (p_place, date_trunc('hour', p_at) + floor(extract(minute from p_at) / 10) * interval '10 minutes', 1)
    on conflict (place_id, bucket) do update set n = place_bucket_counts.n + 1;
$$;
revoke all on function public._bump_counts(text, timestamptz) from public, anon, authenticated;

-- ---------------------------------------------------------------- RPC: record a visit
-- p_at lets an offline-queued check-in keep its real time (accepted only up to 12 h back).
create or replace function public.record_visit(
  p_place text, p_lat double precision, p_lng double precision,
  p_accuracy double precision default null, p_at timestamptz default null)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_uid   uuid := auth.uid();
  v_place places%rowtype;
  v_at    timestamptz := coalesce(p_at, now());
  v_dist  double precision;
  v_id    bigint;
begin
  if v_uid is null then
    raise exception 'sign-in required' using errcode = '28000';
  end if;
  select * into v_place from places where id = p_place;
  if not found then
    return jsonb_build_object('status', 'unknown_place');
  end if;
  if v_at < now() - interval '12 hours' or v_at > now() + interval '5 minutes' then
    return jsonb_build_object('status', 'expired');
  end if;
  if p_lat is null or p_lng is null then
    return jsonb_build_object('status', 'no_location');
  end if;

  v_dist := distance_m(p_lat, p_lng, v_place.lat, v_place.lng);
  if v_dist > v_place.radius_m + least(greatest(coalesce(p_accuracy, 50), 0), 100) then
    return jsonb_build_object('status', 'too_far', 'distance_m', round(v_dist));
  end if;

  if (select count(*) from visits where user_id = v_uid and visited_at > now() - interval '1 hour') >= 40 then
    return jsonb_build_object('status', 'rate_limited');
  end if;

  insert into visits (user_id, place_id, kind, day, visited_at, distance_m)
  values (v_uid, p_place, case v_place.kind when 'pandal' then 'checkin' else 'ate' end,
          (v_at at time zone 'Asia/Kolkata')::date, v_at, round(v_dist))
  on conflict (user_id, place_id, day) do nothing
  returning id into v_id;

  if v_id is not null then
    perform _bump_counts(p_place, v_at);
  end if;

  return jsonb_build_object(
    'status', case when v_id is null then 'duplicate' else 'counted' end,
    'distance_m', round(v_dist),
    'today', coalesce((select n from place_day_counts where place_id = p_place and day = ist_today()), 0),
    'visits', coalesce((select visits from place_counters where place_id = p_place), 0));
end $$;

-- ---------------------------------------------------------------- RPC: publish a photo / video
-- The client uploads to storage first (under <uid>/...), then registers the media here.
create or replace function public.add_photo(
  p_place text, p_path text, p_thumb_path text, p_media_type text,
  p_caption text default null, p_lat double precision default null,
  p_lng double precision default null, p_accuracy double precision default null)
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

  insert into photos (user_id, place_id, media_type, path, thumb_path, caption, on_site, distance_m)
  values (v_uid, p_place, p_media_type, p_path, p_thumb_path,
          nullif(left(btrim(coalesce(p_caption, '')), 140), ''), v_on, round(v_dist))
  returning id into v_id;

  insert into place_counters (place_id, photos) values (p_place, 1)
    on conflict (place_id) do update set photos = place_counters.photos + 1;

  return jsonb_build_object('status', 'ok', 'id', v_id, 'on_site', v_on);
end $$;

-- ---------------------------------------------------------------- RPC: like / report / delete
create or replace function public.toggle_like(p_photo uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare v_uid uuid := auth.uid(); v_liked boolean; v_likes integer;
begin
  if v_uid is null then raise exception 'sign-in required' using errcode = '28000'; end if;
  if not exists (select 1 from photos where id = p_photo and not hidden) then
    return jsonb_build_object('status', 'not_found');
  end if;
  delete from photo_likes where photo_id = p_photo and user_id = v_uid;
  if found then
    v_liked := false;
    update photos set likes = greatest(likes - 1, 0) where id = p_photo returning likes into v_likes;
  else
    insert into photo_likes (photo_id, user_id) values (p_photo, v_uid);
    v_liked := true;
    update photos set likes = likes + 1 where id = p_photo returning likes into v_likes;
  end if;
  return jsonb_build_object('status', 'ok', 'liked', v_liked, 'likes', v_likes);
end $$;

-- Three distinct reports hide a photo until a moderator reviews it in the dashboard.
create or replace function public.report_photo(p_photo uuid, p_reason text default null) returns jsonb
language plpgsql security definer set search_path = public as $$
declare v_uid uuid := auth.uid(); v_reports integer; v_place text;
begin
  if v_uid is null then raise exception 'sign-in required' using errcode = '28000'; end if;
  insert into photo_reports (photo_id, user_id, reason) values (p_photo, v_uid, left(p_reason, 60))
    on conflict do nothing;
  if not found then
    return jsonb_build_object('status', 'already_reported');
  end if;
  update photos set reports = reports + 1, hidden = hidden or reports + 1 >= 3
    where id = p_photo returning reports, place_id into v_reports, v_place;
  if v_reports >= 3 then
    update place_counters set photos = greatest(photos - 1, 0)
      where place_id = v_place and v_reports = 3;
  end if;
  return jsonb_build_object('status', 'ok', 'hidden', coalesce(v_reports, 0) >= 3);
end $$;

create or replace function public.delete_photo(p_photo uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare v_uid uuid := auth.uid(); v_row photos%rowtype;
begin
  if v_uid is null then raise exception 'sign-in required' using errcode = '28000'; end if;
  select * into v_row from photos where id = p_photo and user_id = v_uid;
  if not found then return jsonb_build_object('status', 'not_found'); end if;
  delete from photos where id = p_photo;
  if not v_row.hidden then
    update place_counters set photos = greatest(photos - 1, 0) where place_id = v_row.place_id;
  end if;
  -- The client removes the storage objects itself (storage policy: owners may delete).
  return jsonb_build_object('status', 'ok', 'path', v_row.path, 'thumb_path', v_row.thumb_path);
end $$;

revoke all on function public.record_visit(text, double precision, double precision, double precision, timestamptz),
  public.add_photo(text, text, text, text, text, double precision, double precision, double precision),
  public.toggle_like(uuid), public.report_photo(uuid, text), public.delete_photo(uuid) from public, anon;
grant execute on function public.record_visit(text, double precision, double precision, double precision, timestamptz),
  public.add_photo(text, text, text, text, text, double precision, double precision, double precision),
  public.toggle_like(uuid), public.report_photo(uuid, text), public.delete_photo(uuid) to authenticated;

-- ---------------------------------------------------------------- storage
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('moments', 'moments', true, 20971520,
        array['image/jpeg', 'image/webp', 'video/mp4', 'video/webm', 'video/quicktime'])
on conflict (id) do update set public = excluded.public, file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "moments: owners upload into their folder" on storage.objects;
create policy "moments: owners upload into their folder" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'moments' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "moments: owners delete their files" on storage.objects;
create policy "moments: owners delete their files" on storage.objects
  for delete to authenticated
  using (bucket_id = 'moments' and (storage.foldername(name))[1] = auth.uid()::text);

-- ---------------------------------------------------------------- housekeeping
-- 10-minute buckets older than two days are only needed for "last hour". Prune them on a schedule
-- (Dashboard → Database → Cron, or pg_cron): select public.prune_buckets();
create or replace function public.prune_buckets() returns integer
language sql security definer set search_path = public as $$
  with d as (delete from place_bucket_counts where bucket < now() - interval '2 days' returning 1)
  select count(*)::integer from d
$$;
revoke all on function public.prune_buckets() from public, anon, authenticated;
