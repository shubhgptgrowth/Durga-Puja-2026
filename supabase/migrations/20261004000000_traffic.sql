-- Kolkata Traffic Police puja notices, collected by the `traffic-fetch` Edge Function.
-- The function runs in Mumbai (ap-south-1): kolkatatrafficpolice.gov.in doesn't answer requests from outside India.
-- Anyone can read the relevant notices; only the function (service role) writes.

create table if not exists public.traffic_notices (
  url        text primary key,
  title      text not null,
  page       text,
  relevant   boolean not null default false,
  first_seen timestamptz not null default now(),
  last_seen  timestamptz not null default now()
);
alter table public.traffic_notices enable row level security;
drop policy if exists traffic_notices_read on public.traffic_notices;
create policy traffic_notices_read on public.traffic_notices for select to anon, authenticated using (relevant);
grant select on public.traffic_notices to anon, authenticated;

-- One row per run, for the throttle and for checking the fetcher works. Service role only (no policies).
create table if not exists public.traffic_fetch_log (
  id       bigserial primary key,
  at       timestamptz not null default now(),
  ok       boolean not null,
  region   text,
  pages    jsonb,
  links    int,
  relevant int,
  error    text
);
alter table public.traffic_fetch_log enable row level security;

-- The Edge Function writes as service_role (tables made through the Management API don't get Supabase's default grants).
do $$ begin
  grant select, insert, update on public.traffic_notices to service_role;
  grant select, insert on public.traffic_fetch_log to service_role;
  grant usage, select on sequence public.traffic_fetch_log_id_seq to service_role;
exception when undefined_object then raise notice 'no service_role here (local tests)';
end $$;

-- Freshness for the app: when the fetcher last reached the site.
create or replace function public.traffic_status()
returns json language sql stable security definer set search_path = public as $$
  select json_build_object(
    'last_ok', (select max(at) from traffic_fetch_log where ok),
    'last_try', (select max(at) from traffic_fetch_log));
$$;
grant execute on function public.traffic_status() to anon, authenticated;

-- The schedule (pg_cron + pg_net calling the function every 3 hours) is created by the
-- `traffic-backend` workflow, which knows the project URL. These extensions exist on hosted Supabase.
do $$ begin
  create extension if not exists pg_net;
  create extension if not exists pg_cron;
exception when others then raise notice 'pg_net/pg_cron not available here (fine for local tests)';
end $$;
