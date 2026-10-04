-- My Pujo across phones and browsers.
--
-- Every browser signs in anonymously, so a new browser is a new user. Progress (steps per day, pandals,
-- food stops, check-ins, name and goal; never the phone number) is backed up under a personal Pujo code.
-- Opening the code (or its link) on another browser joins that browser to the same backup; from then on
-- both keep it up to date. The app merges before saving, so devices never wipe each other's progress.

create table if not exists public.progress (
  code        text primary key check (code ~ '^PUJO-[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}$'),
  data        jsonb not null default '{}',
  updated_at  timestamptz not null default now()
);
create table if not exists public.progress_members (
  user_id  uuid primary key,
  code     text not null references public.progress (code) on delete cascade,
  joined   timestamptz not null default now()
);
create table if not exists public.progress_claims (    -- guesses at someone's code are rate limited
  user_id  uuid not null,
  at       timestamptz not null default now()
);
create index if not exists progress_claims_recent on public.progress_claims (user_id, at desc);
alter table public.progress enable row level security;
alter table public.progress_members enable row level security;
alter table public.progress_claims enable row level security;
revoke all on public.progress, public.progress_members, public.progress_claims from anon, authenticated;

-- 8 characters from 32 unambiguous letters and digits (no 0/O, 1/I): ~40 bits.
create or replace function public._new_pujo_code() returns text language plpgsql as $$
declare
  abc text := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  c   text;
begin
  loop
    c := 'PUJO-';
    for i in 1..8 loop
      c := c || substr(abc, 1 + floor(random() * 32)::int, 1);
      if i = 4 then c := c || '-'; end if;
    end loop;
    exit when not exists (select 1 from public.progress where code = c);
  end loop;
  return c;
end $$;
revoke all on function public._new_pujo_code() from public, anon, authenticated;

-- Save this browser's (already merged) progress; creates the code on first save.
create or replace function public.save_progress(p_data jsonb)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_uid  uuid := auth.uid();
  v_code text;
begin
  if v_uid is null then raise exception 'sign-in required' using errcode = '28000'; end if;
  if p_data is null or jsonb_typeof(p_data) <> 'object' then return jsonb_build_object('status', 'bad_data'); end if;
  if octet_length(p_data::text) > 300000 then return jsonb_build_object('status', 'too_big'); end if;
  select code into v_code from progress_members where user_id = v_uid;
  if v_code is null then
    v_code := _new_pujo_code();
    insert into progress (code, data) values (v_code, p_data);
    insert into progress_members (user_id, code) values (v_uid, v_code);
  else
    update progress set data = p_data, updated_at = now() where code = v_code;
  end if;
  return jsonb_build_object('status', 'ok', 'code', v_code);
end $$;

-- What's saved for this browser's code (null before the first save).
create or replace function public.load_progress()
returns jsonb language sql stable security definer set search_path = public as $$
  select jsonb_build_object('status', 'ok', 'code', p.code, 'data', p.data, 'updated_at', p.updated_at)
  from progress_members m join progress p using (code) where m.user_id = auth.uid()
$$;

-- Join this browser to a code typed in or opened from a link; returns that progress to merge in.
create or replace function public.claim_progress(p_code text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare
  v_uid  uuid := auth.uid();
  v_code text := upper(btrim(coalesce(p_code, '')));
  v_old  text;
  r      record;
begin
  if v_uid is null then raise exception 'sign-in required' using errcode = '28000'; end if;
  if (select count(*) from progress_claims where user_id = v_uid and at > now() - interval '1 hour') >= 10 then
    return jsonb_build_object('status', 'rate_limited');
  end if;
  insert into progress_claims (user_id) values (v_uid);
  v_code := regexp_replace(v_code, '^(PUJO)?-?([A-Z0-9]{4})-?([A-Z0-9]{4})$', 'PUJO-\2-\3');
  select * into r from progress where code = v_code;
  if not found then return jsonb_build_object('status', 'not_found'); end if;
  select code into v_old from progress_members where user_id = v_uid;
  insert into progress_members (user_id, code) values (v_uid, v_code)
    on conflict (user_id) do update set code = excluded.code, joined = now();
  -- This browser's own earlier backup, if nobody else uses it any more, is folded into the app's merge and dropped.
  if v_old is not null and v_old <> v_code and not exists (select 1 from progress_members where code = v_old) then
    delete from progress where code = v_old;
  end if;
  return jsonb_build_object('status', 'ok', 'code', r.code, 'data', r.data);
end $$;

revoke all on function public.save_progress(jsonb), public.load_progress(), public.claim_progress(text) from public, anon;
grant execute on function public.save_progress(jsonb), public.load_progress(), public.claim_progress(text) to authenticated;
