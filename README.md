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
| `app/` | Static PWA (vanilla JS + Leaflet, vendored). Works offline once it has loaded. English and বাংলা |
| `app/core.js` | DOM-free maths shared with the tests: routing, crowd, fitness, GPS filter, step detector, share links |
| `tests/` | Python pipeline tests, JS unit tests (`tests/js`), and a Playwright mobile end-to-end test (`tests/e2e/smoke.mjs`) |

## Quick start

```bash
npm ci                                 # dev only: Playwright for the e2e test
npm run build                          # python -m pipeline → app/data/guide.json (+ guide.geojson, BUILD_REPORT.md)
npm test                               # Python pipeline tests + JS unit tests
npx playwright install chromium        # once
npm run test:e2e                       # iPhone-size end-to-end run, screenshots in ./screenshots
npm run serve                          # http://localhost:8123 (open it on your phone or in devtools)
```

The end-to-end test starts its own server. It:
* walks every tab, a curated trail, and a time-budgeted custom route
* opens a shared route link and checks it produces the same stops
* simulates a GPS walk and accelerometer steps
* switches to Bengali and dark mode
* reloads **offline**, and checks for horizontal overflow and console errors

## The pipeline

| Stage | Module | Does |
|---|---|---|
| 1 ingest | `ingest.py` | CSV → typed records (`a\|b` lists, ints, bools) |
| 2 validate | `validate.py` | Required fields, duplicate IDs, Kolkata bounding box, zone and station references, enums, near-duplicate pins. **Fails the build** on errors |
| 3 enrich | `enrich.py` | Nearest metro, the 2 nearest parking spots, food within 800 m (falls back to 2 km), quiet hours per puja day, zone centroids, boxes and entry stations |
| 4 plan | `plan.py` | A walking order for each zone (nearest-neighbour + 2-opt), plus 6 curated multi-zone itineraries with timed stops, crowd-adjusted dwell, metro hops, steps and kcal |
| 5 emit | `emit.py` | `guide.json` (content-hashed version), `guide.geojson`, `BUILD_REPORT.md` |

CI (`.github/workflows/pipeline.yml`) runs two jobs:

* **Data:** Python tests, data validation, a rebuild, and a check that **fails if the committed `guide.json` is stale**.
* **App:**
  * JS unit tests, including a parity test: the in-app planner must produce exactly the pipeline's route for every zone, plus step and crowd parity and Bengali coverage.
  * The mobile end-to-end test. Its screenshots are uploaded as an artifact.

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
  * live GPS walk tracking, with fixes discarded if accuracy is worse than 35 m or speed is above 10 km/h (an auto or cab)
  * **steps from the phone's motion sensor** when it's available. iOS asks for permission when the walk starts. Steps only count after a run of 4, so a bump doesn't count. Otherwise steps are estimated from GPS distance ÷ your stride.
  * kcal from MET values, a daily goal ring and auto check-in within 80 m
  * a "next stop" prompt for the active plan
  * 12 badges and a day-by-day history

  Everything stays in `localStorage` on the device.
* **Share:** any route can be shared as a link (`#plan=…` or `#trail=…`). It uses the phone's share sheet, or copies the link to the clipboard. Whoever opens it gets the same route.
* **বাংলা:** a one-tap language toggle in the header. It translates the UI, plus pandal, zone, day and trail names. Highlights and notes stay in English for now.
* **Resilience:**
  * the guide data is network-first, so fixes pushed during the festival reach people, and "Guide updated" shows when they do
  * the cached copy is used offline, with an offline notice
  * the screen stays awake while tracking
  * cards work with the keyboard, and screen readers get labels

Map tiles come from © OpenStreetMap contributors / © CARTO. For heavy
production traffic, use your own tile key or provider.

## Deploy

**Current (free):** GitHub Pages at https://shubhgptgrowth.github.io/Durga-Puja-2026/.
`.github/workflows/deploy.yml` publishes `app/` on every push to the default
branch, after the tests and data validation pass. Pushes to other branches are
skipped. If Pages is ever switched off, turn it back on under Settings → Pages →
Source: **GitHub Actions**.

`app/` is a fully static site with relative paths, so it can move to Netlify,
Cloudflare Pages or a custom domain later without any code changes. Before the
production launch, swap the CARTO tile URL in `app/app.js` for a keyed tile provider.

## Data disclaimer

Coordinates, timings and parking details are curated from public knowledge and
are **approximate**. Every record ships with `verified=false` until someone
checks it on the ground. Organisers, themes and traffic rules change every
year, so check locally and follow the Kolkata Police advisories.
