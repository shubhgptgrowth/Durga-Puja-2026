# Which map to connect

The app needs four things from a map stack:

1. **Base map tiles** that stay fast and affordable through puja-week traffic spikes, ideally with Bengali labels.
2. **Search and places** for Kolkata addresses.
3. **Walking directions** between pandals.
4. **Turn-by-turn navigation** on the phone.

## Recommendation

| Layer | Use | Why |
|---|---|---|
| Base map, search and routing | **Ola Maps** (Krutrim), rendered with MapLibre GL | Indian map data and Indian addresses, a free tier aimed at Indian developers (no card needed), and vector tiles with Bengali labels |
| Turn-by-turn navigation | **Google Maps deep links** (already in the app) | Free, with no API key and no quota. People already have the Google Maps app and trust its live traffic |
| Offline and fallback | **OpenStreetMap via Protomaps** (self-hosted PMTiles of the Kolkata box) | Zero per-request cost and unlimited loads. It can be cached on the phone and works when the network is jammed |

Don't build on the **Google Maps JavaScript API**. Its Essentials tier includes 10,000 free dynamic map loads a month, then charges about $7 per 1,000. A popular puja app would pass 10,000 loads in a single evening.

## Free tiers (checked October 2026; confirm at sign-up)

| Provider | Free allowance | Over the limit |
|---|---|---|
| Ola Maps | Published free monthly quota. Third-party summaries vary between 100k events and 500k calls a month shared across all APIs | Billed per event |
| MapTiler Cloud | Free plan, with figures reported as 5,000 sessions or 100,000 requests a month, non-commercial | Maps stop until next month |
| Stadia Maps | 200,000 credits a month (1 tile = 1 credit), non-commercial | Requests are refused, with no charges |
| Google Maps Platform | 10,000 Dynamic Maps loads a month (Essentials) | About $7 per 1,000 |
| Self-hosted Protomaps | No limit; you pay only for static hosting | — |

## What the app uses now (October 2026)

**A self-hosted Protomaps vector map.**
* At deploy time, `scripts/build_tiles.sh` extracts Kolkata and Howrah (zoom 0–15) from the latest Protomaps OpenStreetMap build into one `.pmtiles` file.
* It's published at `tiles/kolkata-<build>.pmtiles`, with a `tiles/kolkata.json` manifest, and the app draws it with `protomaps-leaflet` (in `app/vendor/`).
* Light and dark styles follow the theme, and street names switch to Bengali with the app language (where OSM has `name:bn`).

**Why it scales:**
* It's one static file that browsers read in small byte ranges. There are no keys, quotas or per-load fees.
* Behind Cloudflare ([HOSTING.md](HOSTING.md)), the ranges are served from the edge.
* The service worker keeps the ranges you've viewed, so those areas work offline.

**Safety net:**
* The deploy only publishes the file after `tests/e2e/map_tiles.mjs` confirms it renders. Otherwise it publishes a stub manifest.
* If the manifest is empty or the file can't be read, the app quietly uses the CARTO raster tiles as before.

Ola Maps remains an option for search and routing APIs later. Turn-by-turn navigation still hands off to Google Maps.

## How to switch

* **Any raster provider** (MapTiler, Stadia, or Ola raster if your plan includes it): change `map.light`, `map.dark` and `map.attribution` in `app/config.js`. No code changes.
* **Vector tiles with Bengali labels** (Ola Maps or MapTiler vector, Protomaps): swap the renderer from Leaflet to MapLibre GL JS. All map code lives in `makeMap()` and `pinIcon()` in `app/ui.js`, plus the marker layers in `views/explore.js` and `views/plan.js`. It's a contained change once an API key is available.
* **In-app walking polylines** (optional): the planner currently draws straight dashed legs between stops and hands navigation to Google Maps. The Ola or OpenRouteService directions APIs could draw the actual lanes. Cache each leg, because the free quotas are per request.

Sources: [Ola Maps pricing](https://maps.olakrutrim.com/pricing), [Google Maps Platform pricing](https://mapsplatform.google.com/pricing/), [Stadia Maps pricing](https://stadiamaps.com/pricing/), [MapTiler free tier summary](https://freetier.co/directory/products/maptiler).
