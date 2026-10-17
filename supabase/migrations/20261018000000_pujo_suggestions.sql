-- "Add a missing pujo": visitors suggest a pandal the guide doesn't list (name, area, landmark, optionally where
-- they are standing). Suggestions wait as 'pending' until the team checks them and adds the pujo to
-- data/raw/pandals.csv (or the seeds), then marks them 'added' or 'rejected'. No phone or e-mail is collected.
-- The team reads them in the dashboard: Table editor, schema "analytics", view pujo_suggestions.

create table if not exists public.pujo_suggestions (
  id            uuid primary key default gen_random_uuid(),
  name          text not null check (char_length(name) between 3 and 80),
  area          text not null check (char_length(area) between 2 and 80),
  landmark      text check (char_length(landmark) <= 160),
  note          text check (char_length(note) <= 240),
  lat           double precision check (lat between 21.5 and 23.5),
  lng           double precision check (lng between 87.5 and 89.5),
  accuracy_m    integer,
  status        text not null default 'pending' check (status in ('pending', 'added', 'rejected')),
  submitted_by  uuid not null,
  created_at    timestamptz not null default now(),
  reviewed_at   timestamptz
);
create index if not exists pujo_suggestions_user on public.pujo_suggestions (submitted_by, created_at desc);
create index if not exists pujo_suggestions_pending on public.pujo_suggestions (created_at desc) where status = 'pending';
alter table public.pujo_suggestions enable row level security;
revoke all on public.pujo_suggestions from anon, authenticated;

create or replace function public.suggest_pujo(
  p_name text, p_area text, p_landmark text default null, p_note text default null,
  p_lat double precision default null, p_lng double precision default null, p_accuracy double precision default null)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_uid uuid := auth.uid();
  v_id  uuid;
  v_lat double precision := p_lat;
  v_lng double precision := p_lng;
begin
  if v_uid is null then raise exception 'sign-in required' using errcode = '28000'; end if;
  if char_length(btrim(coalesce(p_name, ''))) < 3 then return jsonb_build_object('status', 'bad_name'); end if;
  if char_length(btrim(coalesce(p_area, ''))) < 2 then return jsonb_build_object('status', 'bad_area'); end if;
  if v_lat is null or v_lng is null or v_lat not between 21.5 and 23.5 or v_lng not between 87.5 and 89.5 then
    v_lat := null; v_lng := null;
  end if;
  if (select count(*) from pujo_suggestions where submitted_by = v_uid and created_at > now() - interval '24 hours') >= 10 then
    return jsonb_build_object('status', 'rate_limited');
  end if;
  insert into pujo_suggestions (name, area, landmark, note, lat, lng, accuracy_m, submitted_by)
  values (left(btrim(p_name), 80), left(btrim(p_area), 80),
          nullif(left(btrim(coalesce(p_landmark, '')), 160), ''), nullif(left(btrim(coalesce(p_note, '')), 240), ''),
          v_lat, v_lng, case when v_lat is null then null else round(least(greatest(coalesce(p_accuracy, 0), 0), 5000)) end, v_uid)
  returning id into v_id;
  return jsonb_build_object('status', 'pending', 'id', v_id);
end $$;
revoke all on function public.suggest_pujo(text, text, text, text, double precision, double precision, double precision) from public, anon;
grant execute on function public.suggest_pujo(text, text, text, text, double precision, double precision, double precision) to authenticated;

-- The team's review (SQL editor only; not callable from the app).
create or replace function public.review_pujo_suggestion(p_id uuid, p_status text) returns jsonb
language plpgsql security definer set search_path = public as $$
begin
  if p_status not in ('pending', 'added', 'rejected') then return jsonb_build_object('status', 'bad_status'); end if;
  update pujo_suggestions set status = p_status, reviewed_at = now() where id = p_id;
  if not found then return jsonb_build_object('status', 'not_found'); end if;
  return jsonb_build_object('status', 'ok');
end $$;
revoke all on function public.review_pujo_suggestion(uuid, text) from public, anon, authenticated;

create schema if not exists analytics;
drop view if exists analytics.pujo_suggestions;
create view analytics.pujo_suggestions as
  select s.id, s.status, s.name, s.area, s.landmark, s.note, s.lat, s.lng, s.accuracy_m,
         case when s.lat is not null then 'https://maps.google.com/?q=' || s.lat || ',' || s.lng end as map,
         (select count(*) from pujo_suggestions o where lower(btrim(o.name)) = lower(btrim(s.name))) as times_suggested,
         s.created_at
  from public.pujo_suggestions s
  order by (s.status = 'pending') desc, s.created_at desc;
revoke all on analytics.pujo_suggestions from anon, authenticated;
