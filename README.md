# Pujo Parikrama 2026 🪔

A mobile-first guide to **Durga Puja 2026 pandal hopping in Kolkata** (Shashthi 17 Oct → Dashami 21 Oct).

It covers:
* walkable zones, and routes ordered by an on-device planner
* food and parking
* live, crowd-sourced check-ins
* location-tagged photo and video moments
* a built-in step tracker

It works in English and বাংলা.

**Live (free GitHub Pages):** https://shubhgptgrowth.github.io/Durga-Puja-2026/

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
| `data/raw/` | **Source of truth.** Zones, pandals, food, parking and transit as CSV. `geo_source=osm` marks pins confirmed against OpenStreetMap |
| `pipeline/` | Stdlib-only Python: ingest → validate → enrich → plan → emit, plus `audit` and `audit_apply` for OSM coordinate checks |
| `supabase/` | Migration (tables, RLS, RPCs, storage policies), generated seed, and the local stack config |
| `app/` | Static PWA in vanilla JS ES modules, with Leaflet vendored. `views/` holds one module per tab |
| `tests/` | Python pipeline tests, JS unit tests, SQL rule tests, and a Playwright mobile e2e test with a fake Supabase |

## The app

Five tabs:

| Tab | What it does |
|---|---|
| **Home** | The overview. A hero card shows the chosen puja day and when it's quietest. Below it: search (English or Bengali), quick actions, **Trending now** (live check-ins), **Closest to you**, **Good to visit now** (famous pandals with the shortest queues at this hour), zone cards, latest moments, and trails |
| **Explore** | A map with Pandals, Food and Parking segments, and zone chips. The pandal list can be sorted by fame, shortest queue, distance or most check-ins now. Food has filters (veg, budget, sweets, street, open now). Parking shows car advice per zone and an "I parked here" spot saver |
| **Plan** | Curated trails, or a time-budgeted custom route. Routes export to Google Maps in legs of up to 3 waypoints, and can be shared as a link |
| **Moments** | A community photo and video feed with zone and "taken at the place" filters. It has likes and reports, and an upload button |
| **Me** | The step tracker (motion sensor, or GPS distance as a fallback), auto check-in, pandals visited, food logged, 13 badges, history and settings |

**Pandal and eatery sheets** show:
* live counts: visits, today, last hour
* a check-in or **I ate here** button, verified by GPS (too far away, and it offers a private "just for me" mark instead)
* directions
* a crowd-by-hour chart
* metro and parking
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

## CI

* **data:** tests, validation, a rebuild, and checks that the bundle and seed are fresh.
* **app:** JS unit tests, including parity with the pipeline and translation coverage, plus mobile e2e.
* **community:** SQL rule tests, then e2e against a **real** local Supabase (`supabase start`).
* **deploy:** publishes `app/` to Pages on every push to the default branch, then verifies the live site.

## Data disclaimer

Themes, timings and traffic rules change every year. The app says so, and asks people to check locally.
