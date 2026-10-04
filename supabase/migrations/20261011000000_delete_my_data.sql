-- "Delete all my data" (My Pujo → Settings), promised by app/privacy.html.
-- Removes everything tied to the signed-in user: progress backup (unless another of their devices still
-- shares it… which is them too, so it goes), name and phone, ratings, likes, reports, check-ins, offers
-- they submitted, their photos (rows here; the app deletes the files, which it owns), and the account itself
-- (guest or Google). Place totals (visits, photos) are anonymous counts and stay. The consent log keeps
-- one "withdrawn" line with the time, as the record that the number was erased.
create or replace function public.delete_my_data() returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v_uid   uuid := auth.uid();
  v_files text[];
begin
  if v_uid is null then raise exception 'sign-in required' using errcode = '28000'; end if;

  delete from progress where code in (select code from progress_members where user_id = v_uid);  -- members cascade
  delete from progress_claims where user_id = v_uid;

  if exists (select 1 from profiles where user_id = v_uid) then
    delete from profiles where user_id = v_uid;
    insert into consent_log (user_id, action) values (v_uid, 'withdrawn');
  end if;

  delete from place_ratings where user_id = v_uid;
  update photos p set likes = greatest(p.likes - 1, 0) from photo_likes l where l.photo_id = p.id and l.user_id = v_uid;
  delete from photo_likes where user_id = v_uid;
  delete from photo_reports where user_id = v_uid;
  delete from visits where user_id = v_uid;
  delete from food_offers where submitted_by = v_uid;

  select coalesce(array_agg(x), '{}') into v_files
  from (select path as x from photos where user_id = v_uid union all select thumb_path from photos where user_id = v_uid) f;
  update place_counters c set photos = greatest(c.photos - n, 0)
  from (select place_id, count(*) as n from photos where user_id = v_uid and not hidden and tag is null group by place_id) d
  where c.place_id = d.place_id;
  delete from photos where user_id = v_uid;

  if to_regclass('auth.users') is not null then
    execute 'delete from auth.users where id = $1' using v_uid;
  end if;
  return jsonb_build_object('status', 'ok', 'files', to_jsonb(v_files));
end $$;
revoke all on function public.delete_my_data() from public, anon;
grant execute on function public.delete_my_data() to authenticated;
