# Pujo Parikrama 2026 🪔

A mobile-first guide to **Durga Puja 2026 pandal hopping in Kolkata**
(Shashthi 17 Oct → Dashami 21 Oct). It splits the city into walkable zones and
covers:

* routes, ordered by an on-device planner
* what to eat near each pandal
* where to park, or which metro to take instead
* a built-in **fitness tracker** that counts your steps and auto-checks you in at pandals

```
data/raw/*.csv  ──►  python -m pipeline  ──►  app/data/guide.json  ──►  app/ (PWA)
```

| Path | What |
|---|---|
| [`docs/SCOPE.md`](docs/SCOPE.md) | Project scope: personas, v1 features, data model, fitness maths, roadmap |
| `data/raw/` | **Source of truth.** Zones, pandals, food, parking and transit as CSV (editable in a spreadsheet) |
| `pipeline/` | Stdlib-only Python: ingest → validate → enrich → plan → emit |
| `app/` | Static PWA (vanilla JS + Leaflet, vendored). Works offline once it has loaded |
| `tests/` | Pipeline unit tests, plus a Playwright mobile smoke test (`tests/e2e/smoke.mjs`) |

## Quick start

```bash
python -m pipeline                    # build app/data/guide.json (+ guide.geojson, BUILD_REPORT.md)
python -m unittest discover -s tests  # run the pipeline tests
python -m http.server -d app 8000     # open http://localhost:8000 on your phone or in desktop devtools
```

Mobile smoke test. Needs Playwright with Chromium, and the server above running on port 8123:

```bash
python -m http.server -d app 8123 &
node tests/e2e/smoke.mjs http://localhost:8123/ screenshots
```

## The pipeline

| Stage | Module | Does |
|---|---|---|
| 1 ingest | `ingest.py` | CSV → typed records (`a\|b` lists, ints, bools) |
| 2 validate | `validate.py` | Required fields, duplicate IDs, Kolkata bounding box, zone and station references, enums, near-duplicate pins. **Fails the build** on errors |
| 3 enrich | `enrich.py` | Nearest metro, the 2 nearest parking spots, food within 800 m (falls back to 2 km), quiet hours per puja day, zone centroids, boxes and entry stations |
| 4 plan | `plan.py` | A walking order for each zone (nearest-neighbour + 2-opt), plus 6 curated multi-zone itineraries with timed stops, crowd-adjusted dwell, metro hops, steps and kcal |
| 5 emit | `emit.py` | `guide.json` (content-hashed version), `guide.geojson`, `BUILD_REPORT.md` |

CI (`.github/workflows/pipeline.yml`) runs the tests, validates the data,
rebuilds the bundle and **fails if the committed `guide.json` is stale**.

### Editing data

1. Edit a CSV in `data/raw/`. A Google Sheet exported to CSV works fine.
2. Run `python -m pipeline`. Validation errors name the exact row and field.
3. Commit the CSV and `app/data/` together.

Once a pandal's coordinates have been checked on the ground, set `verified=true` on that row.

## The app

* **Explore:** a map plus zone chips and a pandal list. Sort by fame, by least
  crowded at a chosen hour, or by distance. A detail sheet shows:
  * a 24-hour crowd curve for the selected puja day
  * the quietest hours and the nearest metro
  * food and parking nearby
  * directions, and a manual check-in
* **Plan:** curated trails, or **Build my route**. Pick zones, a start point
  (GPS, a station or a car park), a start time, a minimum star rating, a time
  budget and a pace.
  * The planner orders stops with 2-opt.
  * It adds metro or cab hops between zones that are far apart.
  * When the route is over budget, it drops the stop that costs the most time for its fame.
  * It suggests food along the way and exports the route to Google Maps in legs of up to 3 waypoints.
* **Food:** filter by zone, veg, budget, sweets, street food or open now. Log what you ate.
* **Park:** a car advisory per zone, parking and metro lists, and **"I parked here"** to save your car's spot and walk back to it later.
* **Fit:**
  * live GPS walk tracking, with fixes discarded if accuracy is worse than 35 m or speed is above 10 km/h
  * steps from your height-based stride, and kcal from MET values
  * a daily goal ring and auto check-in within 80 m
  * badges and a day-by-day history

  Everything stays in `localStorage` on the device.

Map tiles come from © OpenStreetMap contributors / © CARTO. For heavy
production traffic, use your own tile key or provider.

## Deploy

`app/` is a fully static site. Any static host works: GitHub Pages
(Settings → Pages → deploy from branch, folder `/app`, or copy it to `/docs`),
Netlify or Cloudflare Pages.

## Data disclaimer

Coordinates, timings and parking details are curated from public knowledge and
are **approximate**. Every record ships with `verified=false` until someone
checks it on the ground. Organisers, themes and traffic rules change every
year, so check locally and follow the Kolkata Police advisories.
