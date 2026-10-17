-- "Most opened this week" on Home (app/views/home.js), for when nobody has checked in yet.
--
-- place_popular: each pandal opened in the app by at least 5 different people in the last 7 days (IST), with that
-- count. Aggregates only: no device ids, no times, and places under 5 people are left out. The app reads it with the
-- anon key, like place_stats. Idempotent: safe to re-run.

create or replace view public.place_popular as
  select place_id, count(distinct device_id)::integer as people_7d
  from public.events
  where name = 'place_open' and kind = 'pandal' and place_id is not null and day > public.ist_today() - 7
  group by place_id
  having count(distinct device_id) >= 5
  order by 2 desc
  limit 12;

revoke all on public.place_popular from public;
grant select on public.place_popular to anon, authenticated;
