-- Reach measurement for the marketing push (docs/marketing/PLAN.md).
-- Counts distinct devices that open the app, per IST day, and which link brought them
-- (?src=ig_bio, wa_channel, qr_<place>, ...). The device id is a random UUID the app keeps in
-- localStorage. It is deliberately not an auth user, so a visit doesn't count towards Supabase's
-- monthly-active-user quota. No names, phones or locations are stored.
-- Idempotent: safe to re-run.

create table if not exists public.app_opens (
  device_id uuid not null,
  day       date not null,
  src       text not null,           -- link that opened the app that day
  first_src text not null,           -- link that first brought this person, as remembered by the device
  opens     integer not null default 1,
  first_at  timestamptz not null default now(),
  primary key (device_id, day)
);
create index if not exists app_opens_day on public.app_opens (day);
alter table public.app_opens enable row level security;
revoke all on public.app_opens from anon, authenticated;

create or replace function public._clean_src(p text) returns text
language sql immutable as $$
  select case
    when p is null or btrim(p) = '' then 'direct'
    when lower(btrim(p)) ~ '^[a-z0-9_]{1,40}$' then lower(btrim(p))
    else 'other' end
$$;

-- RPC: one row per device per day; later opens that day only bump the counter. Callable without signing in.
drop function if exists public.track_open(text, text);
create or replace function public.track_open(p_device uuid, p_src text default null, p_first_src text default null)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_day date := public.ist_today();
  v_new boolean;
begin
  if p_device is null then return jsonb_build_object('status', 'no_device'); end if;
  insert into app_opens (device_id, day, src, first_src)
    values (p_device, v_day, _clean_src(p_src), _clean_src(coalesce(p_first_src, p_src)))
    on conflict (device_id, day) do update set opens = least(app_opens.opens + 1, 1000)
    returning (xmax = 0) into v_new;
  return jsonb_build_object('status', case when v_new then 'counted' else 'repeat' end, 'day', v_day);
end $$;

revoke all on function public.track_open(uuid, text, text) from public;
grant execute on function public.track_open(uuid, text, text) to anon, authenticated;

-- Report for the team (marketing workflow, via the Management API). Not callable from the app.
-- Counts are devices, a close proxy for people.
create or replace function public.growth_report(p_days integer default 30) returns jsonb
language sql stable security definer set search_path = public as $$
  with firsts as (   -- each person's first day and the link that first brought them
    select distinct on (device_id) device_id, day as first_day, first_src
    from app_opens order by device_id, day, first_at
  ), days as (
    select o.day, count(*) as people, count(*) filter (where f.first_day = o.day) as new_people, sum(o.opens) as opens
    from app_opens o join firsts f using (device_id)
    where o.day > public.ist_today() - p_days
    group by o.day
  ), sources as (
    select first_src as src, count(*) as people from firsts group by first_src
  ), today_src as (
    select src, count(*) as people from app_opens where day = public.ist_today() group by src
  )
  select jsonb_build_object(
    'generated_at', now(),
    'devices_total', (select count(*) from firsts),
    'devices_today', (select count(*) from app_opens where day = public.ist_today()),
    'checked_in_people', (select count(distinct user_id) from visits),
    'by_day', coalesce((select jsonb_agg(jsonb_build_object('day', day, 'people', people, 'new', new_people, 'opens', opens) order by day) from days), '[]'),
    'by_first_source', coalesce((select jsonb_agg(jsonb_build_object('src', src, 'people', people) order by people desc) from sources), '[]'),
    'today_by_source', coalesce((select jsonb_agg(jsonb_build_object('src', src, 'people', people) order by people desc) from today_src), '[]')
  )
$$;
revoke all on function public.growth_report(integer) from public, anon, authenticated;
revoke all on function public._clean_src(text) from public, anon, authenticated;
