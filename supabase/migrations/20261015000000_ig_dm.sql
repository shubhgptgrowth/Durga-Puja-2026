-- Comment-to-DM ledger for the `ig-dm` Edge Function: whoever comments "PUJO" on one of our recent Instagram posts gets
-- the guide in one private reply. pg_cron calls the function every 5 minutes (GitHub's cron ran up to 10 hours late).
-- Service role only: no policies, nothing here is readable from the app.

create table if not exists public.ig_dm_sent (
  comment_id text primary key,
  username   text,
  media_id   text,
  status     text not null,               -- 'sent', or 'already' when Instagram says the comment already has a private reply
  at         timestamptz not null default now()
);
alter table public.ig_dm_sent enable row level security;

-- Last seen comment count per post, so a run only reads the comments of posts that got new ones.
create table if not exists public.ig_dm_media (
  media_id       text primary key,
  comments_count int not null,
  at             timestamptz not null default now()
);
alter table public.ig_dm_media enable row level security;

do $$ begin
  grant select, insert, update on public.ig_dm_sent, public.ig_dm_media to service_role;
exception when undefined_object then raise notice 'no service_role here (local tests)';
end $$;

do $$ begin
  create extension if not exists pg_net;
  create extension if not exists pg_cron;
exception when others then raise notice 'pg_net/pg_cron not available here (fine for local tests)';
end $$;
