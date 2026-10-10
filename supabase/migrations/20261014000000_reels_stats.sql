-- Pujo Reels numbers for the team dashboard (app/reels.js, docs/product/ANALYTICS.md).
--
-- The app records reel_open (detail "<reel>:<tile|next>"), reel_watch (detail "<reel>:<seconds>", sent when the player
-- closes) and reel_pandal (a tap from a reel to its pandal). reels_report() turns them into plays, viewers, minutes
-- watched (each watch capped at 15 minutes, so a player left open doesn't count as an hour) and the top reels.
-- dashboard() is redefined with a 'reels' block; everything else in it is unchanged. Idempotent: safe to re-run.

create or replace function public.reels_report(p_days integer default 1) returns jsonb
language sql stable security definer set search_path = public as $$
  with ev as (select * from public.events where day > public.ist_today() - p_days and name in ('reel_open', 'reel_watch', 'reel_pandal')),
  w as (select split_part(detail, ':', 1) as reel,
               least(case when split_part(detail, ':', 2) ~ '^[0-9]{1,6}$' then split_part(detail, ':', 2)::int else 0 end, 900) as secs
        from ev where name = 'reel_watch')
  select jsonb_build_object(
    'opens', (select count(*) from ev where name = 'reel_open'),
    'viewers', (select count(distinct device_id) from ev where name = 'reel_open'),
    'watch_minutes', (select round(coalesce(sum(secs), 0) / 60.0, 1) from w),
    'pandal_taps', (select count(*) from ev where name = 'reel_pandal'),
    'top', coalesce((select jsonb_agg(x order by x.minutes desc) from (
        select reel, count(*) as plays, round(sum(secs) / 60.0, 1) as minutes from w group by 1 order by 3 desc limit 10) x), '[]'))
$$;
revoke all on function public.reels_report(integer) from public, anon, authenticated;

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
    'reels', public.reels_report(d),
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
