-- site_counts() also returns `today`: devices that used the app today (IST), for the header ticker.
create or replace function public.site_counts() returns jsonb
language sql stable security definer set search_path = public as $$
  select jsonb_build_object(
    'live', (select count(*) from presence where last_seen > now() - interval '5 minutes'),
    'today', (select count(*) from presence where day = ist_today()),
    'people', (select count(distinct device_id) from app_opens))
$$;
revoke all on function public.site_counts() from public;
grant execute on function public.site_counts() to anon, authenticated;
