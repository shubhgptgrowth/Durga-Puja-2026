# Pujo Parikrama 2026 🪔

A mobile-first guide to **Durga Puja 2026 pandal hopping in Kolkata** (Shashthi 17 Oct → Dashami 21 Oct).

It covers:
* 96 pandals in 5 regions (North, Central, South, East, Howrah), each split into walkable areas, with routes ordered by an on-device planner
* photos of past idols and pandals, and of each eatery's signature dishes
* how to get there by metro, bus, share auto or cab
* food and parking
* live, crowd-sourced check-ins
* location-tagged photo and video moments
* a built-in step tracker

It works in English and বাংলা.

**Live (free GitHub Pages):** https://shubhgptgrowth.github.io/Durga-Puja-2026/ · daily marketing kit: [/kit/](https://shubhgptgrowth.github.io/Durga-Puja-2026/kit/)

```
data/raw/*.csv ─► python -m pipeline ─► app/data/guide.json ─► app/ (static PWA)
                       │                                        │
                       └─► supabase/seed.sql ─► Supabase (check-ins, moments) ◄┘
```

| Path | What |
|---|---|
| [`docs/SCOPE.md`](docs/SCOPE.md) | Scope: personas, features, data model, fitness maths, roadmap |
| [`docs/COMMUNITY.md`](docs/COMMUNITY.md) | Community backend: how counts are verified, setup in 10 minutes, free-tier budget |
| [`docs/MAPS.md`](docs/MAPS.md) | Which map provider to connect, and why |
| [`docs/MARKETING.md`](docs/MARKETING.md) | Instagram + WhatsApp playbook: goal, capacity checklist, daily routine, calendar, partner scripts, reach report |
| `data/raw/` | **Source of truth.** Regions, areas (`zones.csv`), pandals, food, parking and transit as CSV. `geo_source=osm` marks pins confirmed against OpenStreetMap |
| `pipeline/` | Stdlib-only Python: ingest → validate → enrich → plan → emit. Also `audit` and `audit_apply` for OSM coordinate checks, and `discover` / `discovered` for pulling more pandals, transit and photos from open data |
| `data/seeds/`, `data/discovered/` | Well-known pujas to look up, curated auto routes, and the raw open-data pulls (OSM, Wikimedia Commons) |
| `marketing/` | Daily content kit (`kit.py` plan + captions, `render.mjs` images, QR posters), the reach report and optional Instagram auto-posting |
| `supabase/` | Migration (tables, RLS, RPCs, storage policies), generated seed, and the local stack config |
| `app/` | Static PWA in vanilla JS ES modules, with Leaflet vendored. `views/` holds one module per tab |
| `tests/` | Python pipeline tests, JS unit tests, SQL rule tests, and a Playwright mobile e2e test with a fake Supabase |

## The app

Five tabs:

| Tab | What it does |
|---|---|
| **Home** | The overview. A hero card shows the chosen puja day and when it's quietest. Below it: search (English or Bengali), quick actions, **Trending now** (live check-ins), **Closest to you**, **Good to visit now** (famous pandals with the shortest queues at this hour), region chips with area cards, latest moments, and trails |
| **Explore** | A map with Pandals, Food and Parking segments, and a two-level filter: pick a region, then an area inside it. The pandal list can be sorted by fame, shortest queue, distance or most check-ins now. Food has filters (veg, budget, sweets, street, open now). Parking shows car advice per zone and an "I parked here" spot saver |
| **Plan** | Curated trails, or a time-budgeted custom route. Choose areas grouped by region, and a start point from a searchable picker (my location, any station, pandal or car park). Each leg says whether to take the metro, a bus, a share auto or a cab. Routes export to Google Maps in legs of up to 3 waypoints, and can be shared as a link |
| **Moments** | A community photo and video feed with region/area and "taken at the place" filters. It has likes and reports, and an upload button |
| **Me** | The step tracker (motion sensor, or GPS distance as a fallback), auto check-in, pandals visited, food logged, 13 badges, history and settings |

**Pandal and eatery sheets** show:
* live counts: visits, today, last hour
* a check-in or **I ate here** button, verified by GPS (too far away, and it offers a private "just for me" mark instead)
* directions
* a crowd-by-hour chart
* a photo gallery (pandals: past years' idols and pandals; eateries: popular dishes), credited to Wikimedia Commons
* getting there: nearest metro, bus stops and routes, common share-auto routes, auto stands, parking, and a Google transit directions link
* nearby food
* that place's moments

## Quick start

```bash
npm ci                         # dev only: Playwright
npm run build                  # python -m pipeline → app/data/*, supabase/seed.sql
npm test                       # Python + JS unit tests
tests/sql/run.sh               # community rules on a throwaway local Postgres
npx playwright install chromium && npm run test:e2e   # iPhone-size e2e against a fake Supabase
npm run serve                  # http://localhost:8123
```

Community features stay off until `app/config.js` has a Supabase URL and anon key. Setup is in [docs/COMMUNITY.md](docs/COMMUNITY.md).

## Data accuracy

* `python -m pipeline.audit` (the **geo-audit** workflow) checks every pin against OpenStreetMap. It uses Overpass for stations and Nominatim for everything else.
* `python -m pipeline.audit_apply data/audit/geo_audit.json` applies only confident matches: the right kind of feature, a strong name match, and under 2 km. It never uses road or neighbourhood centroids.
* The October 2026 audit corrected 58 of 119 pins:
  * all 24 metro and rail stations, some of which were up to 1.1 km off
  * 25 pandals, for example Suruchi by 1.5 km, Badamtala by 1.2 km and Tridhara by 670 m
  * 5 eateries and 4 malls
* The rest are marked `curated` and still need a ground check. OSM-confirmed pins get a tighter 250 m check-in radius (350 m otherwise).

## More pandals, transit and photos

The **discover** workflow (`.github/workflows/discover.yml`, run by hand) runs `python -m pipeline.discover pandals|transit|photos`:
* **pandals:** every Durga Puja tagged in OpenStreetMap around Kolkata, plus a Nominatim lookup for each well-known puja in `data/seeds/pandal_seeds.csv`
* **transit:** OSM bus and share-taxi routes, their stops, and taxi/auto stands
* **photos:** Wikimedia Commons images per pandal and per signature dish

The results are committed to `data/discovered/`. Then run `python -m pipeline.discovered pandals` to merge confident new pandals into `data/raw/pandals.csv` (as `osm-discovered`). Duplicates, non-pujas and weak matches are skipped. Transit and photos are attached at build time. `data/raw/photo_blocklist.csv` removes wrong photo matches.

Limits:
* OSM bus coverage in Kolkata is thin. Bus stops and routes appear only where they are mapped.
* Share-auto routes are mostly the curated list in `data/seeds/auto_routes.csv`.
* Every sheet has a Google transit directions link to fill the gaps.
* Dish photos are representative of the dish, not taken at that shop.
* After adding places, re-run the **supabase-setup** workflow so the backend knows them.

## CI

* **data:** tests, validation, a rebuild, and checks that the bundle and seed are fresh.
* **app:** JS unit tests, including parity with the pipeline and translation coverage, plus mobile e2e.
* **community:** SQL rule tests, then e2e against a **real** local Supabase (`supabase start`).
* **deploy:** publishes `app/` to Pages on every push to the default branch and every morning (05:45 IST, plus 16:00 on puja days), with the content kit at `/kit/`, then verifies the live site.
* **marketing-report:** the daily reach report (devices by day and by link, check-ins). **marketing-publish:** optional Instagram auto-posting, off by default.

## Data disclaimer

Themes, timings and traffic rules change every year. The app says so, and asks people to check locally.
