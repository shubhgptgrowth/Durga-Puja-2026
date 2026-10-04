-- traffic_notices: anon reads only relevant rows and cannot write; the log is invisible to anon.
begin;
insert into public.traffic_notices (url, title, relevant) values
  ('https://kolkatatrafficpolice.gov.in/a.pdf', 'Traffic arrangements for Durga Puja', true),
  ('https://kolkatatrafficpolice.gov.in/b.pdf', 'Tender notice', false);
insert into public.traffic_fetch_log (ok, region, links, relevant) values (true, 'ap-south-1', 2, 1);
set local role anon;
do $$ begin
  if (select count(*) from public.traffic_notices) <> 1 then raise exception 'anon should see only relevant notices'; end if;
  begin
    if (select count(*) from public.traffic_fetch_log) <> 0 then raise exception 'anon must not read the fetch log'; end if;
  exception when insufficient_privilege then null;  -- no grant locally; on hosted Supabase RLS hides every row
  end;
  if (public.traffic_status()->>'last_ok') is null then raise exception 'traffic_status should report the last run'; end if;
  begin
    insert into public.traffic_notices (url, title, relevant) values ('x', 'spam', true);
    raise exception 'anon insert should fail';
  exception when insufficient_privilege then null;
  end;
end $$;
select 'traffic ok';
rollback;
