-- Usage analytics and the live "people here now" count.
--
-- The app sends small anonymous batches (device id from app_opens, no sign-in, no location, no name):
--   track(device, events) every ~60 s while the page is visible. It also marks the device as present.
-- live = devices seen in the last 5 minutes. site_counts() gives live and all-time people to the app.
--
-- Event names (app/analytics.js): view, place_open, directions, transit, checkin, rate, share, sfx,
-- music, filter, lang, plan, trail, moment, install. place_id / kind / detail add context.
--
-- The `analytics` schema is the team's directory: views over the events, visible in the Supabase
-- dashboard (Table editor → schema "analytics") and in the analytics-report workflow. Not exposed to the app.

create table if not exists public.presence (
  device_id  uuid primary key,
  last_seen  timestamptz not null default now(),
  view       text,
  day        date not null default public.ist_today(),
  day_events integer not null default 0
);
create index if not exists presence_recent on public.presence (last_seen desc);

create table if not exists public.events (
  id         bigint generated always as identity primary key,
  device_id  uuid not null,
  at         timestamptz not null default now(),
  day        date not null default public.ist_today(),
  name       text not null check (name ~ '^[a-z_]{1,24}$'),
  view       text check (char_length(view) <= 16),
  place_id   text check (char_length(place_id) <= 60),
  kind       text check (kind in ('pandal', 'food', 'parking')),
  detail     text check (char_length(detail) <= 60)
);
create index if not exists events_day_name on public.events (day, name);
create index if not exists events_place on public.events (place_id, name) where place_id is not null;

alter table public.presence enable row level security;
alter table public.events enable row level security;
revoke all on public.presence, public.events from anon, authenticated;

-- Each device may log up to 1,500 events a day; extra ones are dropped quietly.
create or replace function public.track(p_device uuid, p_events jsonb default '[]')
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_today date := ist_today();
  v_room  integer;
  v_view  text;
  v_n     integer := 0;
begin
  if p_device is null then
    return jsonb_build_object('status', 'no_device');
  end if;
  if jsonb_typeof(p_events) <> 'array' then p_events := '[]'; end if;
  select e->>'view' into v_view from jsonb_array_elements(p_events) e where e->>'view' is not null order by (e->>'t')::bigint desc nulls last limit 1;
  insert into presence as pr (device_id, last_seen, view, day, day_events) values (p_device, now(), left(v_view, 16), v_today, 0)
  on conflict (device_id) do update set last_seen = now(), view = coalesce(left(v_view, 16), pr.view),
    day = v_today, day_events = case when pr.day = v_today then pr.day_events else 0 end
  returning 1500 - day_events into v_room;

  if v_room > 0 and jsonb_array_length(p_events) > 0 then
    insert into events (device_id, at, day, name, view, place_id, kind, detail)
    select p_device,
           least(now(), greatest(now() - interval '1 hour', coalesce(to_timestamp((e->>'t')::double precision / 1000), now()))),
           v_today, e->>'n', left(e->>'view', 16), left(e->>'place', 60),
           case when e->>'kind' in ('pandal', 'food', 'parking') then e->>'kind' end, left(e->>'d', 60)
    from (select e from jsonb_array_elements(p_events) e limit least(50, v_room)) x
    where coalesce(e->>'n', '') ~ '^[a-z_]{1,24}$';
    get diagnostics v_n = row_count;
    update presence set day_events = day_events + v_n where device_id = p_device;
  end if;
  return jsonb_build_object('status', 'ok', 'stored', v_n,
    'live', (select count(*) from presence where last_seen > now() - interval '5 minutes'));
end $$;
revoke all on function public.track(uuid, jsonb) from public;
grant execute on function public.track(uuid, jsonb) to anon, authenticated;

-- Real numbers only: people active in the last 5 minutes, and everyone who has opened the app.
create or replace function public.site_counts() returns jsonb
language sql stable security definer set search_path = public as $$
  select jsonb_build_object(
    'live', (select count(*) from presence where last_seen > now() - interval '5 minutes'),
    'people', (select count(distinct device_id) from app_opens))
$$;
revoke all on function public.site_counts() from public;
grant execute on function public.site_counts() to anon, authenticated;

-- ---------------------------------------------------------------- the team's directory
create schema if not exists analytics;
revoke all on schema analytics from anon, authenticated;

create or replace view analytics.live as
  select (select count(*) from public.presence where last_seen > now() - interval '5 minutes') as now_5min,
         (select count(*) from public.presence where last_seen > now() - interval '1 hour') as last_hour,
         (select count(*) from public.presence where day = public.ist_today()) as today,
         (select count(distinct device_id) from public.app_opens) as all_time;

create or replace view analytics.live_by_page as
  select coalesce(view, '?') as page, count(*) as people
  from public.presence where last_seen > now() - interval '5 minutes' group by 1 order by 2 desc;

create or replace view analytics.daily as
  select day, name as event, count(*) as events, count(distinct device_id) as people
  from public.events group by 1, 2 order by 1 desc, 3 desc;

create or replace view analytics.pages as
  select day, coalesce(detail, view) as page, count(*) as views, count(distinct device_id) as people
  from public.events where name = 'view' group by 1, 2 order by 1 desc, 3 desc;

-- Every location: pandals and eateries (from places) plus parking and anything else seen in events.
create or replace view analytics.places as
  with e as (
    select place_id, max(kind) as kind,
           count(*) filter (where name = 'place_open') as opens,
           count(distinct device_id) filter (where name = 'place_open') as people,
           count(*) filter (where name = 'place_open' and at > now() - interval '24 hours') as opens_24h,
           count(*) filter (where name = 'directions') as directions,
           count(*) filter (where name = 'transit') as transit,
           count(*) filter (where name = 'share') as shares,
           count(*) filter (where name = 'checkin') as checkin_taps
    from public.events where place_id is not null group by place_id)
  select coalesce(p.id, e.place_id) as place_id, coalesce(p.kind, e.kind) as kind, p.name, p.zone,
         coalesce(e.opens, 0) as opens, coalesce(e.people, 0) as people, coalesce(e.opens_24h, 0) as opens_24h,
         coalesce(e.directions, 0) as directions, coalesce(e.transit, 0) as transit, coalesce(e.shares, 0) as shares,
         coalesce(c.visits, 0) as verified_visits, r.rating, coalesce(r.ratings, 0) as ratings
  from public.places p
  full join e on e.place_id = p.id
  left join public.place_counters c on c.place_id = coalesce(p.id, e.place_id)
  left join public.place_rating_stats r on r.place_id = coalesce(p.id, e.place_id)
  order by opens desc, verified_visits desc;

create or replace view analytics.sounds as
  select day, name as source, coalesce(detail, '?') as what, count(*) as taps, count(distinct device_id) as people
  from public.events where name in ('sfx', 'music') group by 1, 2, 3 order by 1 desc, 4 desc;

create or replace view analytics.actions as
  select day, name as action, coalesce(detail, '') as detail, count(*) as times, count(distinct device_id) as people
  from public.events where name not in ('view', 'place_open', 'sfx', 'music') group by 1, 2, 3 order by 1 desc, 4 desc;

revoke all on all tables in schema analytics from anon, authenticated;

-- One call for the report workflow (Management API).
create or replace function public.analytics_report(p_days integer default 1) returns jsonb
language sql stable security definer set search_path = public, analytics as $$
  with ev as (select * from public.events where day > public.ist_today() - p_days)
  select jsonb_build_object(
    'days', p_days,
    'live', (select to_jsonb(l) from analytics.live l),
    'people', (select count(distinct device_id) from ev),
    'events', (select count(*) from ev),
    'pages', coalesce((select jsonb_agg(x order by x.views desc) from (
        select coalesce(detail, view) as page, count(*) as views, count(distinct device_id) as people from ev where name = 'view' group by 1) x), '[]'),
    'places', coalesce((select jsonb_agg(x) from (
        select ev.place_id, max(ev.kind) as kind, max(p.name) as name,
               count(*) filter (where ev.name = 'place_open') as opens,
               count(*) filter (where ev.name = 'directions') as directions,
               count(*) filter (where ev.name = 'checkin') as checkins
        from ev left join public.places p on p.id = ev.place_id
        where ev.place_id is not null group by ev.place_id order by 4 desc, 5 desc limit 25) x), '[]'),
    'sounds', coalesce((select jsonb_agg(x order by x.taps desc) from (
        select name as source, coalesce(detail, '?') as what, count(*) as taps, count(distinct device_id) as people
        from ev where name in ('sfx', 'music') group by 1, 2) x), '[]'),
    'actions', coalesce((select jsonb_agg(x order by x.times desc) from (
        select name as action, count(*) as times, count(distinct device_id) as people
        from ev where name not in ('view', 'place_open', 'sfx', 'music') group by 1) x), '[]'))
$$;
revoke all on function public.analytics_report(integer) from public, anon, authenticated;
