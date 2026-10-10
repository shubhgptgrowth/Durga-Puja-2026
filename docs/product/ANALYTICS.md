# Usage analytics and the live count

## What the app records

`app/analytics.js` sends small anonymous batches (one request a minute while the page is open, plus one when
it's hidden). Each event has the random device id also used for the reach count, the page, and optionally a
place id, its kind and a short detail. **No name, phone, location or sign-in.** Browsers with *Do Not Track*
or *Global Privacy Control* send nothing. Each device can log at most 1,500 events a day.

| Event | When | place / detail |
|---|---|---|
| `view` | a tab is shown | detail = page (home, explore, plan, moments, me) |
| `place_open` | a pandal / eatery / parking page opens | place id, kind |
| `directions`, `transit` | the Directions or public-transport link is tapped | the open place |
| `checkin` | "I'm here" / "I ate here" | place, result (counted, too_far…) |
| `rate` | a rating is submitted | place, stars |
| `share` | WhatsApp, link or story card | the open place, how |
| `sfx` | dhak / shankh tap pads and the sticky 🥁 🐚 | dhak, shankh |
| `music` | radio play, auto-start, pause, "open in YouTube Music/Spotify" | station:song |
| `filter` | Map tab: section, area, sort, food chips, list/map | which |
| `plan`, `trail` | a route is built, a 6-day plan day or ready-made trail is opened | zones / trail id |
| `lang`, `moment` | language switched, a photo/video posted | en/bn/hi, image/video |
| `reel_open` | a Pujo Reel starts (Home strip, Moments, or "Next reel") | its pandal; detail = reel id:tile/next |
| `reel_watch` | the reel player closes | its pandal; detail = reel id:seconds watched |
| `reel_pandal` | "Open this pandal" from a reel | the pandal; detail = reel id |

## The live dashboard

The dashboard's **Pujo Reels** card shows plays, viewers, minutes watched (each watch counted up to 15 minutes) and taps
through to a pandal, plus the reels watched longest (`supabase/migrations/*_reels_stats.sql`).

**pujoparikramaguide.in/kit/dashboard/** shows everything below on one page, refreshed every minute: who is on
the site now (and on which screen), people reached against the 1,00,000 goal, visitors per day (new and
returning), activity by hour, which channels and `?src=` links brought people in, app screens, actions, the
most-opened places, and music and sound taps. Pick Today, 7, 14 or 30 days at the top; every chart has a table view.

It is a public page that shows nothing without a key. The key lives in the database, so it never touches the repo:

1. After the dashboard migration is applied (run **Actions → supabase-setup** once), open Supabase → **SQL editor**
   and run `select key from private.dashboard_access;`.
2. Open `pujoparikramaguide.in/kit/dashboard/#key=<that key>` and bookmark it, or paste the key into the page. The
   part after `#` is never sent to any server; the page keeps the key on that device and clears it from the address bar.
3. To share it with a teammate, send them the link privately. To shut everyone out, run
   `select public.rotate_dashboard_key();` in the SQL editor; the old key stops working at once.

The page calls `public.dashboard(key, days)`, which returns aggregates only (no device ids). A wrong key gets
`{"ok": false}` and runs no query.

## Where to look (the directory)

Supabase dashboard → **Table editor → schema `analytics`** (or SQL editor). Read-only views:

| View | What |
|---|---|
| `analytics.live` | on the site now (last 5 min), last hour, today, all time |
| `analytics.live_by_page` | where the people online right now are |
| `analytics.places` | **every location**: pandals and eateries (all, even with no events), parking and anything else seen in events. Opens, people, opens in the last 24 h, directions, transit, shares, verified visits, rating |
| `analytics.pages` | views and people per page per day |
| `analytics.sounds` | dhak / shankh taps and radio plays per day |
| `analytics.actions` | everything else per day (shares, filters, plans…) |
| `analytics.daily` | every event type per day |

None of these can be read with the app's public key (tested in `tests/sql/analytics_test.sql`).

A daily summary also lands in **Actions → analytics-report** (22:10 IST, or run it by hand with any number of
days). It holds aggregates only. Note that the repo is public, so anyone can read that summary; if that's a
concern, use the dashboard views instead and disable the schedule.

## The live count on Home

"🟢 N people on Pujo Parikrama right now" is the number of devices that sent a heartbeat in the last 5
minutes. "N+ have planned their pujo here" is every device that has opened the app (rounded down to the
hundred). Each part shows only once it is big enough (20 live, 500 all-time), so small numbers aren't shown.
The live part updates every minute with a short count-up animation.

These are real counts on purpose. A padded or simulated "users online" number would be a false claim to
visitors, and the CCPA's dark-pattern guidelines (2023) treat inflated popularity claims as a "false urgency"
practice.

## Volume

At 100k concurrent phones that is ~1,700 tiny requests a second at the peak. Each is a single upsert plus
an insert. If the Supabase plan starts to strain, raise `BEAT_MS` in `app/analytics.js` (120 s halves it)
and widen the live window to match.
