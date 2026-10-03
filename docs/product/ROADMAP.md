# Product roadmap: the app at shubhgptgrowth.github.io/Durga-Puja-2026

This track covers everything the app does: data, features, backend, hosting and quality.
Marketing lives in [../marketing/](../marketing/). The seam between the two tracks is listed at the end.

**Owns:** `app/`, `pipeline/`, `data/`, `supabase/`, `tests/`, and the `pipeline`, `deploy`, `discover`, `geo-audit` and `supabase-setup` workflows.

## Key dates

| Date | Milestone | What must be true |
|---|---|---|
| **10 Oct (Mahalaya)** | Marketing launch push | Capacity upgrades in place (P0). No known broken pins in the top 40 pandals |
| **16 Oct (Panchami)** | Code freeze | Only data fixes and hotfixes after this. Every change still goes through CI |
| 17–21 Oct | Puja days | Watch errors, check-ins and the backend quota daily. Fix data within hours |
| 22 Oct → | Wind-down | Bijoya recap, downgrade paid plans, write the retro and next year's list |

## Where the app is today (3 Oct)

* **Coverage:** 107 pandals in 5 regions and 13 areas, 29 eateries, 14 car parks, 24 metro and rail stations, 6 trails.
* **Data quality:**
  * 63 pins come from OpenStreetMap: 32 matched to a named feature, and 31 discovered from tagged pujas.
  * 28 pins are curated by hand and not yet ground-checked.
  * 16 pins are approximate (the centre of their neighbourhood).
  * The 31 OSM-discovered pandals have no Bengali name.
  * 43 pandals have photos.
* **Features:**
  * Region → area filters and a searchable start picker.
  * Getting there by metro, bus or shared auto.
  * Photo galleries with credits.
  * GPS-verified check-ins and "I ate here".
  * Moments: location-tagged photos and videos.
  * A step tracker and badges.
  * English and Bengali, offline-capable.
* **Growth features:** `?src=` tracking, `#p=` direct links, WhatsApp share, story cards, link previews.
* **Quality gates:**
  * 31 Python tests, 20 JS tests and SQL rule tests.
  * A mobile end-to-end test against both a fake and a real Supabase.
  * A live-site check after every deploy.

## Backlog

Each item is a GitHub issue under the [Product track (#1)](https://github.com/shubhgptgrowth/Durga-Puja-2026/issues/1). Labels: `product`, `P0`/`P1`/`P2`, `decision-needed`, `local-help`. Close the issue when an item ships, and update the status here.

Priority: **P0** = before Mahalaya (10 Oct). **P1** = before Shashthi (17 Oct). **P2** = nice to have, or next year.
Status: ⬜ todo · 🟡 in progress · ✅ done · ⏸ waiting on a decision.

### P0: launch-blocking

| # | Item | Why | Status |
|---|---|---|---|
| [P0-1](https://github.com/shubhgptgrowth/Durga-Puja-2026/issues/3) | **Supabase Pro for October** (US$25) | The free plan's 5 GB egress doesn't survive the push. Live counts were already slowed to every 3 minutes | ⏸ owner decision, billing |
| [P0-2](https://github.com/shubhgptgrowth/Durga-Puja-2026/issues/4) | **Hosting that scales**: Cloudflare Pages (free, no bandwidth cap), optionally with a short domain | GitHub Pages has a soft limit of about 100 GB a month. Moving means changing `SITE` in `marketing/kit.py` and the OG tags in `app/index.html` | ⏸ owner decision |
| [P0-3](https://github.com/shubhgptgrowth/Durga-Puja-2026/issues/5) | **Map tiles for scale**: Ola Maps, or self-hosted Protomaps for the Kolkata box | The CARTO tiles are fair-use only (see [MAPS.md](MAPS.md)) | ⬜ |
| [P0-4](https://github.com/shubhgptgrowth/Durga-Puja-2026/issues/6) | **Ground-check the top 40 pandal pins**, starting with the 16 approximate and 28 curated ones | A wrong pin breaks check-in and directions. Approximate pins already get a 600 m check-in radius | ⬜ needs local help |
| [P0-5](https://github.com/shubhgptgrowth/Durga-Puja-2026/issues/8) | **The 5 missing well-known pujas**: Sikdarbagan, Pathuriaghata Panchar Pally, Darjipara, Kestopur Prafulla Kanan, Salkia Sarbojanin | People will search for them | ⬜ needs an address or landmark |
| [P0-6](https://github.com/shubhgptgrowth/Durga-Puja-2026/issues/7) | **Error and quota monitoring**: a client error beacon, and a daily check of Supabase usage in `marketing-report` | So we see breakage on puja nights before users do | ⬜ |

### P1: before Shashthi

| # | Item | Why | Status |
|---|---|---|---|
| [P1-1](https://github.com/shubhgptgrowth/Durga-Puja-2026/issues/9) | **2026 themes**: add each pandal's 2026 theme once committees announce them (usually around Mahalaya) | It's the first thing people ask: "what's the theme this year?" | ⬜ |
| [P1-2](https://github.com/shubhgptgrowth/Durga-Puja-2026/issues/10) | **Bengali names** for the 31 OSM-discovered pandals | The Bengali UI shows English names for them | ⬜ |
| [P1-3](https://github.com/shubhgptgrowth/Durga-Puja-2026/issues/11) | **"Add to home screen" prompt** after a first check-in or a saved plan | Repeat use during the 5 days, and fewer cold loads | ⬜ |
| [P1-4](https://github.com/shubhgptgrowth/Durga-Puja-2026/issues/12) | **Crowd report button**: "How's the queue here? Short / Medium / Long" next to check-in | Turns the crowd curve from a guess into a live signal (Phase 6 in [SCOPE.md](SCOPE.md)) | ⬜ |
| [P1-5](https://github.com/shubhgptgrowth/Durga-Puja-2026/issues/13) | **Howrah coverage**: only 2 pandals today | Howrah is a whole region on the filter | ⬜ |
| [P1-6](https://github.com/shubhgptgrowth/Durga-Puja-2026/issues/14) | **More photos**: 64 pandals have none. Run discover again after the pujas start (fresh Commons uploads), plus moments | Sheets with photos convert better | ⬜ |
| [P1-7](https://github.com/shubhgptgrowth/Durga-Puja-2026/issues/15) | **Moderation view** for moments: hide, report queue | 3 reports auto-hide today; puja-night volume needs a human view | ⬜ |
| [P1-8](https://github.com/shubhgptgrowth/Durga-Puja-2026/issues/16) | **Performance pass**: lazy-load the map on first use, trim `guide.json` (~300 KB) | Slow networks around pandals | ⬜ |
| [P1-9](https://github.com/shubhgptgrowth/Durga-Puja-2026/issues/17) | **Accessibility pass**: contrast in dark mode, screen-reader labels on map pins | Reach older users and family groups | ⬜ |

### P2: later ([#18](https://github.com/shubhgptgrowth/Durga-Puja-2026/issues/18))

| # | Item |
|---|---|
| P2-1 | Offline map pack (PMTiles) for a whole area, downloaded on Wi-Fi |
| P2-2 | Curated bus routes (OSM has only 21 routes for Kolkata) and auto fares |
| P2-3 | Kolkata Traffic Police advisories and road closures, if a feed exists |
| P2-4 | Turn a plan into a shareable group plan ("our pujo route", where friends can vote) |
| P2-5 | Hindi UI |
| P2-6 | A post-puja year-in-review page per device, built from local history |

## How a change ships

1. Branch from `claude/kolkata-durga-puja-guide-4t5xad`, the current default branch.
2. **Data:**
   * Edit `data/raw/*.csv`, or run `discover` → `python -m pipeline.discovered pandals`.
   * Then run `python -m pipeline` and commit the regenerated `app/data/*` and `supabase/seed.sql`.
3. **Code:** edit `app/`, then run the local gates: `npm test`, `tests/sql/run.sh`, `npm run test:e2e`.
4. Push. The `pipeline` workflow runs everything again, including the real-Supabase end-to-end test. `deploy` publishes and then checks the live site.
5. **If places changed, run `supabase-setup`.** Deploy's live check fails until it has run.
6. **App shell or new modules:** bump `VERSION` in `app/sw.js` so phones pick up the new code.

## What marketing relies on (the seam)

Don't break these without telling the marketing track:

| Contract | Where | Used by |
|---|---|---|
| Link codes: `?src=<a-z0-9_ up to 40>` | `app/growth.js` `captureSource()`, `public._clean_src()` | Every post, poster and partner link |
| Direct links: `#p=<place id>` | `app/app.js` | QR posters, WhatsApp shares, comment replies. **Renaming a place id breaks printed posters** |
| Place ids and names | `app/data/guide.json` | `marketing/kit.py` builds every card from it |
| Reach counting | `track_open()`, `growth_report()` in `supabase/migrations/*_growth.sql` | The `marketing-report` workflow |
| Share UI | WhatsApp, Story card and Link buttons on sheets; My Pujo card on the Me tab | The viral loop in the marketing plan |
| `SITE` URL | `marketing/kit.py`, the OG tags in `app/index.html` | All links. Change both together (P0-2) |
