-- Contacts repository: the people who opted in with a name and phone in My Pujo, with the data points
-- the app already has about them, kept in one place for the team.
--
-- What it holds per person (all keyed by their anonymous sign-in id):
--   profiles     name, phone, language, the link that first brought them, device id, consent time
--   consent_log  every grant / update / withdrawal, with no name or phone (proof of consent, DPDP Act)
--   joined in    days the app was opened (app_opens, by device), check-ins, eateries, ratings
--
-- Nobody can read any of it through the public API. The team reads it with contacts_report() through
-- the Management API (the contacts-export workflow, which encrypts the file). Withdrawing consent in the
-- app deletes the profile row at once; the log keeps only "withdrawn" and the time.

alter table public.profiles add column if not exists lang text check (lang in ('en', 'bn', 'hi'));
alter table public.profiles add column if not exists first_src text;
alter table public.profiles add column if not exists device_id uuid;
alter table public.profiles add column if not exists created_at timestamptz not null default now();

create table if not exists public.consent_log (
  id       bigint generated always as identity primary key,
  user_id  uuid not null,
  action   text not null check (action in ('granted', 'updated', 'withdrawn')),
  purpose  text not null default 'pujo_updates',
  at       timestamptz not null default now()
);
create index if not exists consent_log_user on public.consent_log (user_id, at);
alter table public.consent_log enable row level security;
revoke all on public.consent_log from anon, authenticated;

drop function if exists public.save_profile(text, text, boolean);
create or replace function public.save_profile(p_name text, p_phone text, p_consent boolean,
  p_lang text default null, p_src text default null, p_device uuid default null)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_uid   uuid := auth.uid();
  v_phone text := normalize_in_mobile(p_phone);
  v_name  text := nullif(left(btrim(coalesce(p_name, '')), 60), '');
  v_had   boolean;
begin
  if v_uid is null then
    raise exception 'sign-in required' using errcode = '28000';
  end if;
  v_had := exists (select 1 from profiles where user_id = v_uid);
  if not coalesce(p_consent, false) then
    delete from profiles where user_id = v_uid;
    if v_had then insert into consent_log (user_id, action) values (v_uid, 'withdrawn'); end if;
    return jsonb_build_object('status', 'deleted');
  end if;
  if v_phone is null then
    return jsonb_build_object('status', 'bad_phone');
  end if;
  insert into profiles (user_id, name, phone, consent_at, lang, first_src, device_id)
  values (v_uid, v_name, v_phone, now(), case when p_lang in ('en', 'bn', 'hi') then p_lang end, _clean_src(p_src), p_device)
  on conflict (user_id) do update set name = excluded.name, phone = excluded.phone, updated_at = now(),
    lang = coalesce(excluded.lang, profiles.lang), first_src = coalesce(profiles.first_src, excluded.first_src),
    device_id = coalesce(excluded.device_id, profiles.device_id);
  insert into consent_log (user_id, action) values (v_uid, case when v_had then 'updated' else 'granted' end);
  return jsonb_build_object('status', 'ok');
end $$;
revoke all on function public.save_profile(text, text, boolean, text, text, uuid) from public, anon;
grant execute on function public.save_profile(text, text, boolean, text, text, uuid) to authenticated;

-- For the team only (service role / Management API). One row per opted-in person.
create or replace function public.contacts_report()
returns table (name text, phone text, lang text, first_src text, opted_in timestamptz, updated timestamptz,
               days_active integer, last_open date, pandals integer, eateries integer, ratings integer,
               avg_stars numeric, last_visit timestamptz)
language sql stable security definer set search_path = public as $$
  select p.name, p.phone, p.lang,
         coalesce(p.first_src, (select o.first_src from app_opens o where o.device_id = p.device_id order by o.day limit 1)),
         p.consent_at, p.updated_at,
         (select count(*)::int from app_opens o where o.device_id = p.device_id),
         (select max(o.day) from app_opens o where o.device_id = p.device_id),
         (select count(distinct v.place_id)::int from visits v where v.user_id = p.user_id and v.kind = 'checkin'),
         (select count(distinct v.place_id)::int from visits v where v.user_id = p.user_id and v.kind = 'ate'),
         (select count(*)::int from place_ratings r where r.user_id = p.user_id),
         (select round(avg(r.stars), 1) from place_ratings r where r.user_id = p.user_id),
         (select max(v.visited_at) from visits v where v.user_id = p.user_id)
  from profiles p
  order by p.consent_at
$$;
revoke all on function public.contacts_report() from public, anon, authenticated;

-- Counts only, safe to show in a public job summary.
create or replace function public.contacts_summary() returns jsonb
language sql stable security definer set search_path = public as $$
  select jsonb_build_object(
    'contacts', (select count(*) from profiles),
    'new_today', (select count(*) from profiles where (created_at at time zone 'Asia/Kolkata')::date = ist_today()),
    'withdrawn', (select count(*) from consent_log where action = 'withdrawn'),
    'by_lang', coalesce((select jsonb_object_agg(coalesce(lang, '?'), n) from (select lang, count(*) n from profiles group by lang) x), '{}'),
    'by_source', coalesce((select jsonb_object_agg(coalesce(first_src, 'direct'), n) from (select first_src, count(*) n from profiles group by first_src) x), '{}'))
$$;
revoke all on function public.contacts_summary() from public, anon, authenticated;
