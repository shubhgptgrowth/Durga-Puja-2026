-- The team's live dashboard (/kit/dashboard/, docs/product/ANALYTICS.md).
--
-- The page is static and public, so the numbers sit behind a long random key kept in the private schema. Read it
-- once in the Supabase SQL editor:   select key from private.dashboard_access;
-- and open  <site>/kit/dashboard/#key=<key>  (the part after # never leaves the browser). To change it:
--   select public.rotate_dashboard_key();      -- SQL editor only; the old link stops working at once
--
-- dashboard() returns aggregates only (no device ids): the reach report, the usage report, who is online by
-- page, hourly activity for the last 24 hours and check-in totals. A wrong key gets nothing and costs no query.
-- Idempotent: safe to re-run.

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table if not exists private.dashboard_access (
  key        text primary key check (char_length(key) >= 32),
  created_at timestamptz not null default now()
);
revoke all on private.dashboard_access from public, anon, authenticated;
insert into private.dashboard_access (key)
  select replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '')
  where not exists (select 1 from private.dashboard_access);

create or replace function public.rotate_dashboard_key() returns text
language plpgsql security definer set search_path = public, private as $$
declare k text := replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '');
begin
  delete from private.dashboard_access;
  insert into private.dashboard_access (key) values (k);
  return k;
end $$;
revoke all on function public.rotate_dashboard_key() from public, anon, authenticated;

create or replace function public.dashboard(p_key text, p_days integer default 14) returns jsonb
language plpgsql stable security definer set search_path = public, analytics, private as $$
declare d integer := least(greatest(coalesce(p_days, 14), 1), 90);
begin
  if p_key is null or not exists (select 1 from private.dashboard_access where key = p_key) then
    return jsonb_build_object('ok', false);
  end if;
  return jsonb_build_object(
    'ok', true,
    'days', d,
    'generated_at', now(),
    'growth', public.growth_report(d),
    'usage', public.analytics_report(d),
    'live_by_page', coalesce((select jsonb_agg(to_jsonb(x)) from analytics.live_by_page x), '[]'),
    -- people active in each IST hour of the last 24 hours (any event or heartbeat-carrying batch)
    'hourly', coalesce((select jsonb_agg(jsonb_build_object('hour', h, 'people', n) order by h) from (
        select date_trunc('hour', at at time zone 'Asia/Kolkata') as h, count(distinct device_id) as n
        from public.events where at > now() - interval '24 hours' group by 1) x), '[]'),
    'checkins', (select jsonb_build_object(
        'pandal', coalesce(sum(visits) filter (where kind = 'pandal'), 0),
        'food', coalesce(sum(visits) filter (where kind = 'food'), 0),
        'today', coalesce(sum(today), 0)) from public.place_stats));
end $$;
revoke all on function public.dashboard(text, integer) from public;
grant execute on function public.dashboard(text, integer) to anon, authenticated;
