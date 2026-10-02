# Pujo Parikrama 2026 — Project Scope

A mobile-first guide for pandal hopping in Kolkata during Durga Puja 2026.

| Day | Date | Notes |
|---|---|---|
| Mahalaya | Sat 10 Oct 2026 | Many pandals open from here; crowds are light |
| Panchami | Fri 16 Oct | Inaugurations end; the best "early bird" day |
| Shashthi | Sat 17 Oct | Bodhon; crowds build up from the evening |
| Saptami | Sun 18 Oct | Crowds peak |
| Ashtami | Mon 19 Oct | Anjali in the morning, Sandhi Puja. Biggest night |
| Navami | Tue 20 Oct | Very crowded. Last full night |
| Dashami | Wed 21 Oct | Sindoor Khela, then immersion processions. Many pandals close early |

## 1. Problem

Every year millions of people walk Kolkata's streets over five nights, and they
make the same mistakes:

* They zig-zag across the city because they don't know which pandals sit close together.
* They queue for an hour at a blockbuster pandal at 9 pm, when the same pandal is close to empty at 7 am.
* They drive into a no-entry zone and then can't find anywhere to park.
* They miss the legendary food that's a 3-minute walk from the pandal they're standing at.
* They walk 15 km without knowing it, or want to know it and can't track it.

## 2. Users

| Persona | Need |
|---|---|
| **Local family** (car, kids, elders) | Short walks, parking, toilets, low-crowd slots |
| **College group** (metro, all night) | Maximum pandals per hour, cheap food, late-night route |
| **Visitor / NRI / tourist** | "The famous ones", how to get there, what to eat |
| **Fitness-minded walker** | Step and distance goals, a streak, a "puja marathon" |

## 3. Goals for v1 (in scope)

1. **Zones.** The city is split into walkable zones (North, Central, South,
   Behala, Salt Lake & Lake Town, Dum Dum). Each zone is a set of pandals you
   can do on foot in a single outing.
2. **Pandal directory.** Name, zone, theme tags, how famous it is, the best
   time to visit, how crowded it usually gets, the nearest metro, the nearest
   parking, and the food nearby.
3. **Route planner.** Pick zones, a start point (a metro station or your GPS),
   a time budget and a pace. The planner builds an ordered walking route
   (nearest-neighbour plus 2-opt), estimates time, distance, steps and
   calories, and opens it in Google Maps with all the waypoints.
4. **Curated itineraries.** Ready-made routes such as "North Kolkata Heritage
   Trail", "South Heavyweights", "Salt Lake Block Hop" and "All-Nighter
   North→South", built by the pipeline.
5. **Food guide.** Famous eateries and must-try dishes, linked to the pandals
   within walking distance. Filter by veg and by budget.
6. **Parking and transit.** Mall and multi-level parking, park-and-ride metro
   stations, and a no-car advisory for each zone.
7. **Fitness tracker.** Live GPS walk tracking with distance, an estimated
   step count, calories and pace. Pandals are checked in automatically when
   you're within about 80 m. Also: daily goals, badges, and a history of your
   puja days. Everything stays on the device.
8. **Works on a phone in a crowd.** Mobile-first layout, one-thumb bottom
   navigation, offline-capable PWA (data plus app shell are cached; map tiles
   are cached opportunistically), and a low-data mode.

## 4. Out of scope for v1 (backlog)

* Live crowd and queue data. This needs partner feeds or crowdsourcing. The v1 crowd score is a *heuristic* based on day, hour and popularity.
* Live traffic and road closures. The Kolkata Traffic Police advisory is linked instead.
* User accounts, cloud sync and social sharing of walks.
* Turn-by-turn navigation. We hand off to Google Maps or OSM.
* Hindi localisation, and Bengali translations of highlights and notes. The UI and names are in Bengali as of v1.
* Accessibility audit for wheelchair routing.

## 5. Architecture

```
data/raw/*.csv ──► pipeline/ (Python, stdlib only)
   (editable in        1. ingest    CSV → typed records
    Google Sheets)     2. validate  schema, bounding box, refs, duplicates
                       3. enrich    nearest metro/parking, food ≤ 800 m, walk times,
                                    crowd curve per day × hour
                       4. plan      per-zone optimal walking order + curated itineraries
                                    (distance, steps, kcal)
                       5. emit      app/data/guide.json + guide.geojson + build report
                                │
                                ▼
                    app/ (static PWA, no build step)
                    index.html · app.js · styles.css · sw.js
                    Leaflet + OpenStreetMap tiles
                    localStorage for plans, walks and badges
```

Why it's built this way:

* **CSV source of truth.** Volunteers and editors can update pandals in a
  spreadsheet without touching code, and CI rebuilds the bundle.
* **Stdlib-only pipeline.** It's reproducible, has no dependency hell, and runs in CI in about 1 second.
* **Static PWA.** It can be hosted free on GitHub Pages or Netlify. It handles
  the puja-night traffic spike with zero servers and works on patchy 4G.
* **Planning runs on the device too.** The JS planner reuses the same
  algorithm, so plans you build yourself need no network.

## 6. Data model (summary)

| Entity | Key fields |
|---|---|
| `zone` | id, name, centroid, color, vibe, car_advisory, best_metro |
| `pandal` | id, name, zone, lat/lng, tags, popularity (1–5), crowd_base (1–5), best_slot, est_visit_min, est_year |
| `food` | id, name, lat/lng, dishes, type (sweets/street/restaurant), veg, price (₹–₹₹₹), hours |
| `parking` | id, name, lat/lng, kind (mall/multilevel/street/park-ride), capacity, rate_hint |
| `transit` | id, name, line, lat/lng |

> **Data accuracy:** the coordinates and details are curated from public
> knowledge and are approximate. Each record carries a `verified` flag.
> Organisers and themes change every year, and the app always tells users to
> check locally.

## 7. Fitness model

* Steps ≈ distance (m) ÷ stride. Stride = 0.415 × height (default 165 cm → about 0.68 m).
* kcal = MET × weight (kg) × hours. MET is 3.0 for a strolling crowd pace and
  3.8 for a brisk walk. The default weight is 65 kg, and the user can edit it.
* Planned walking distance = haversine × 1.3 detour factor, to account for
  Kolkata's lanes.
* GPS noise filter: a point is dropped if accuracy > 35 m, if the jump is
  under 3 m, or if the implied speed is over 10 km/h. That last check catches
  the moments you hop into a rickshaw.

## 8. Phases

| Phase | Deliverable | Status |
|---|---|---|
| 0 Scope | This doc | ✅ |
| 1 Pipelines | `pipeline/`, raw CSVs, tests, CI | ✅ |
| 2 Mobile visual | `app/` PWA with Explore, Plan, Food, Park and Fit | ✅ |
| 2b Completion | Motion-sensor steps, share links, Bengali UI, network-first data, keyboard access, JS and e2e tests in CI, 53 pandals | ✅ |
| 3 Hosting | Static deploy, a custom domain, and the production tile provider | Next |
| 3b Data hardening | Verify coordinates on the ground, and add more pandals and Bengali highlights | Backlog |
| 4 Live layer | Crowdsourced queue reports, police advisories | Backlog |

## 9. Success metrics

* Average pandals per outing goes up, and walking distance per pandal goes down.
* At least 60 % of planned routes are opened in Maps.
* Fitness: share of users who hit their daily step goal on Ashtami 🙂
