# Community backend: check-ins, "I ate here", moments

The community layer turns individual visits into a shared, live popularity signal:

* **Verified check-ins and "I ate here".** A visit counts publicly only when the phone's GPS shows it is at the place. The allowed distance is the place's radius plus the reported accuracy, capped at 100 m. Each person counts once per place per day.
* **Live counts.** Every pandal and eatery shows *total visits*, *today*, and *in the last hour*. Home has a "Trending now" strip, and Explore can sort by "Most check-ins now".
* **Moments.** Photos and short videos are tagged to a pandal or eatery. A moment taken at the place gets an **On site** badge. People can like and report moments. Three reports hide a moment automatically.

It runs on [Supabase](https://supabase.com) (Postgres, Auth, Storage) and talks to it only over Supabase's REST APIs, with no SDK. If no backend is configured, the app works exactly as before: everything stays local, and Moments shows a "being set up" notice.

## How it is protected

| Concern | Mechanism |
|---|---|
| Fake or inflated counts | Visits go through `record_visit()`, which checks the GPS distance on the server, allows one visit per person per place per day, and caps each person at 40 visits an hour |
| Who is "a person" | Supabase **anonymous sign-in** (no account or email). Each device gets a stable ID that the rules key on |
| Direct table access | RLS is on for every table with **no** policies. Clients can only read the `place_stats` and `photos_feed` views and call the RPCs |
| Location privacy | The coordinates are used once, for the distance check, and only the distance is stored. Photos are re-encoded on the phone, which strips EXIF data, GPS included |
| Bad uploads | The storage bucket allows only JPEG/WebP/MP4/WebM/MOV up to 20 MB. Uploads must go into your own `<uid>/` folder. `add_photo()` rejects files you didn't upload, and caps you at 30 moments a day and 6 in 10 minutes |
| Abuse | Three distinct reports hide a moment. Moderators can review or unhide them in the dashboard (`photos.hidden`, `photo_reports`) |
| Bad networks | Check-ins queue on the phone with their real time and GPS fix, and are accepted up to 12 h late. Moments queue in IndexedDB and upload when the network returns |

## One-time setup (about 10 minutes)

1. Create a free project at <https://supabase.com/dashboard>. Pick the **Mumbai (ap-south-1)** region.
2. **Authentication → Sign In / Providers → turn on "Allow anonymous sign-ins".**
3. **SQL Editor:** paste and run `supabase/migrations/20261002000000_community.sql`, then `supabase/seed.sql`.
   With the Supabase CLI instead: `supabase link --project-ref <ref> && supabase db push`, then run `seed.sql`.
4. **Project Settings → API:** copy the *Project URL* and the *anon / publishable* key into `app/config.js`:
   ```js
   community: { url: 'https://<ref>.supabase.co', anonKey: '<anon key>', ... }
   ```
   Both are meant to be public. Security comes from the rules above, not from hiding the key.
5. Optional: **Database → Cron**, run `select public.prune_buckets();` daily.
6. Push. The deploy workflow publishes the site, and community features switch on automatically.

Whenever `data/raw` changes, run `python -m pipeline` and re-run `supabase/seed.sql`. That keeps the places, radii and coordinates in step with the app. CI fails if the committed seed is stale.

## Free-tier budget

The Supabase Free plan includes 500 MB of database, 1 GB of file storage, 5 GB of uncached egress, and 50,000 monthly active users (anonymous users count). Free projects also **pause after a week of inactivity**. The app is designed to fit within this:

* Feeds load **~40 KB thumbnails**. The full photo (about 300 KB) loads only when someone opens it, and the service worker caches both.
* Count polling reads ~80 small rows every 90 seconds, from counter tables rather than raw visits.

Rough capacity: around 25,000 posted photos fit in storage, and about 100,000 thumbnail views fit in each 5 GB of egress. For puja week, consider the Pro plan (no pausing, much higher quotas). You could also move media to a zero-egress store such as Cloudflare R2 later; only `mediaUrl()` and `upload()` in `app/community.js` would change.

## Testing

* `tests/sql/run.sh`: the rules (distance, once a day, rate limits, RLS, ownership, reports) on a throwaway local Postgres.
* `npm run test:e2e`: the full phone flow against an in-memory fake Supabase (`tests/e2e/fake-supabase.mjs`).
* CI's `community` job runs the same e2e against a **real** local Supabase (`supabase start`) that uses this migration and seed.
