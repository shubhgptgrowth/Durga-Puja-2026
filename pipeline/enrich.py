"""Stage 3: derive zone geometry, nearest metro/parking/food, and crowd windows."""
import json
import re
import tomllib

from . import config
from .discovered import attach_photos, attach_transit, build_archive, transit_bundle, transit_index
from .geo import centroid, haversine_m, walk_m

THEMES = config.RAW_DIR / "themes_2026.csv"
AWARDS = config.RAW_DIR / "awards_2026.toml"
PANJIKA = config.RAW_DIR / "panjika_2026.toml"
HELP = config.ROOT / "data" / "discovered" / "help.json"
# How far to look for each kind of help (a hospital is worth a short ride; a toilet has to be close).
HELP_MAX_M = {"toilets": 1000, "hospitals": 3000, "police": 1500}


def load_awards(path=AWARDS, pandal_ids=None):
    """Award winners by pandal id, newest first, plus the list of awards (data/raw/awards_2026.toml)."""
    if not path.exists():
        return {}, []
    d = tomllib.loads(path.read_text(encoding="utf-8"))
    awards = {a["id"]: {k: a[k] for k in ("id", "name", "short", "url", "announce") if a.get(k)} for a in d.get("award", [])}
    out = {}
    for w in d.get("winner", []):
        where = f"awards_2026.toml: winner {w.get('pandal')!r}"
        if w.get("award") not in awards:
            raise ValueError(f"{where} has an unknown award {w.get('award')!r}")
        if not str(w.get("source", "")).startswith("https://") or not w.get("category") or not isinstance(w.get("year"), int):
            raise ValueError(f"{where} needs a year, a category and an https source")
        if pandal_ids is not None and w["pandal"] not in pandal_ids:
            raise ValueError(f"{where} is not a pandal in the guide")
        out.setdefault(w["pandal"], []).append({"award": w["award"], "year": w["year"], "category": w["category"],
                                                **({"theme": w["theme"]} if w.get("theme") else {}), "source": w["source"]})
    for v in out.values():
        v.sort(key=lambda x: -x["year"])
    return out, list(awards.values())


def load_panjika(path=PANJIKA):
    """Ashtami anjali and Sandhi Puja times from each panjika (data/raw/panjika_2026.toml), or None."""
    if not path.exists():
        return None
    d = tomllib.loads(path.read_text(encoding="utf-8"))
    hhmm = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
    for p in d.get("panjika", []):
        if not (hhmm.match(p.get("sandhi_start", "")) and hhmm.match(p.get("sandhi_end", ""))) or not p.get("source", "").startswith("https://"):
            raise ValueError(f"panjika_2026.toml: {p.get('id')!r} needs sandhi_start/sandhi_end as HH:MM and an https source")
        if p["sandhi_end"] <= p["sandhi_start"]:
            raise ValueError(f"panjika_2026.toml: {p['id']!r} Sandhi Puja ends before it starts")
    if d.get("day") not in {x["id"] for x in config.PUJA_DAYS}:
        raise ValueError(f"panjika_2026.toml: unknown day {d.get('day')!r}")
    return d


def load_help(path=HELP):
    """Public toilets, hospitals and police stations from OpenStreetMap (python -m pipeline.discover help)."""
    if not path.exists():
        return None
    d = json.loads(path.read_text(encoding="utf-8"))
    return {k: d.get(k, []) for k in HELP_MAX_M}


# Not where you'd take someone hurt in a crowd: specialist centres (OpenStreetMap tags them all amenity=hospital).
SPECIALIST = re.compile(r"(?i)matern|\beye\b|netra|ophthalm|dental|diagnostic|dialysis|skin|\bent\b|veterinar|animal")


def _hospital_ok(h):
    name = h.get("name:en") or h.get("name") or ""
    return bool(name) and h.get("emergency") != "no" and not SPECIALIST.search(name)


def help_near(pt, places):
    """The nearest place of each kind within reach: {kind: {name, lat, lng, distance_m, walk_min}}. For hospitals, the
    nearest one with an emergency department wins if it's within reach; otherwise the nearest general hospital."""
    out = {}
    for kind, max_m in HELP_MAX_M.items():
        rows = places.get(kind, [])
        if kind == "hospitals":
            rows = [h for h in rows if _hospital_ok(h)]
            er = [h for h in rows if h.get("emergency") == "yes" and haversine_m(pt, (h["lat"], h["lng"])) <= max_m]
            rows = er or rows
        best = min(((haversine_m(pt, (h["lat"], h["lng"])), h) for h in rows), key=lambda x: x[0], default=None)
        if best and best[0] <= max_m:
            h = best[1]
            out[kind] = {"name": h.get("name:en") or h.get("name") or "", "lat": h["lat"], "lng": h["lng"],
                         "distance_m": round(best[0]), "walk_min": _walk_min(best[0]),
                         **({"emergency": True} if h.get("emergency") == "yes" else {})}
    return out


def load_themes(path=THEMES):
    """This year's pandal themes, each with the report it came from (data/raw/themes_2026.csv).
    Rows for pujas not (yet) in pandals.csv are kept aside until that puja is added."""
    import csv
    if not path.exists():
        return {}
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        r = {k: (v or "").strip() for k, v in r.items()}
        if not r["pandal_id"] or not r["title"] or not r["source"].startswith("https://"):
            raise ValueError(f"themes_2026.csv: {r.get('pandal_id')!r} needs a title and an https source")
        out[r["pandal_id"]] = {k: r[k] for k in ("title", "title_bn", "about", "artist", "source", "source_date") if r[k]}
    return out


def crowd_index(crowd_base, day_factor, hour):
    """Return a 0–100 heuristic crowd level for a pandal at a given day and hour."""
    return min(100, round(crowd_base / 5 * day_factor * config.HOUR_FACTORS[hour % 24] * 100))


def _nearest(point, rows, limit=1, max_m=None):
    scored = sorted(
        ((round(haversine_m(point, (r["lat"], r["lng"]))), r) for r in rows),
        key=lambda t: t[0],
    )
    if max_m is not None:
        scored = [t for t in scored if t[0] <= max_m]
    return scored[:limit]


def _walk_min(m):
    return round(m * config.DETOUR_FACTOR / (config.WALK_KMH_CROWD * 1000 / 60))


def checkin_radius(r):
    """Server-enforced "you are really there" radius. Must match the seed.sql radius_m."""
    if r.get("verified"):
        return config.CHECKIN_RADIUS_VERIFIED_M
    if r.get("geo_source") == "osm":
        return config.CHECKIN_RADIUS_OSM_M
    if r.get("geo_source") == "osm-approx":
        return config.CHECKIN_RADIUS_APPROX_M
    return config.CHECKIN_RADIUS_UNVERIFIED_M


def enrich(data):
    used = {p["zone"] for p in data["pandals"]}
    zones = {z["id"]: dict(z) for z in data["zones"] if z["id"] in used}
    transit, parking, food = data["transit"], data["parking"], data["food"]
    pandals = []
    themes = load_themes()
    winners, awards = load_awards(pandal_ids={p["id"] for p in data["pandals"]})
    help_places = load_help()

    for p in data["pandals"]:
        pt = (p["lat"], p["lng"])
        e = dict(p)

        (metro_d, metro), = _nearest(pt, transit)
        e["nearest_metro"] = {"id": metro["id"], "name": metro["name"], "line": metro["line"],
                              "distance_m": metro_d, "walk_min": _walk_min(metro_d)}

        e["parking"] = [{"id": r["id"], "distance_m": d, "walk_min": _walk_min(d)}
                        for d, r in _nearest(pt, parking, limit=2, max_m=config.NEARBY_PARKING_M)]
        near_food = _nearest(pt, food, limit=4, max_m=config.NEARBY_FOOD_M) or _nearest(pt, food, limit=2, max_m=2000)
        e["food"] = [{"id": r["id"], "distance_m": d, "walk_min": _walk_min(d)} for d, r in near_food]

        # For each puja day, pick the two hours with the lowest crowd index.
        e["quiet_hours"] = {}
        for day in config.PUJA_DAYS:
            ranked = sorted(range(24), key=lambda h: (crowd_index(p["crowd_base"], day["factor"], h), h))
            e["quiet_hours"][day["id"]] = ranked[:2]
        e["peak_crowd"] = crowd_index(p["crowd_base"], 1.1, 20)
        e["checkin_radius_m"] = checkin_radius(p)
        e["best_slot_label"] = config.SLOTS[p["best_slot"]]["label"]
        if p["id"] in themes:
            e["theme_2026"] = themes[p["id"]]
        if p["id"] in winners:
            e["awards"] = winners[p["id"]]
        if help_places:
            e["help"] = help_near(pt, help_places)
        pandals.append(e)

    for zid, z in zones.items():
        members = [p for p in pandals if p["zone"] == zid]
        pts = [(p["lat"], p["lng"]) for p in members]
        c = centroid(pts)
        z["centroid"] = [round(c[0], 5), round(c[1], 5)]
        z["bbox"] = [[min(p[0] for p in pts), min(p[1] for p in pts)],
                     [max(p[0] for p in pts), max(p[1] for p in pts)]]
        z["pandal_ids"] = [p["id"] for p in members]
        z["radius_m"] = round(max(haversine_m(c, p) for p in pts))
        (d, station), = _nearest(c, transit)
        z["entry_station"] = station["id"]
        z["parking_ids"] = [r["id"] for r in parking if r["zone"] == zid]
        z["food_ids"] = [r["id"] for r in food if r["zone"] == zid]
        z["five_star"] = sum(1 for p in members if p["popularity"] == 5)

    # Reverse links: the pandals each eatery serves.
    for f in food:
        f["checkin_radius_m"] = checkin_radius(f)
        (metro_d, metro), = _nearest((f["lat"], f["lng"]), transit)
        f["nearest_metro"] = {"id": metro["id"], "name": metro["name"], "line": metro["line"],
                              "distance_m": metro_d, "walk_min": _walk_min(metro_d)}
        f["near_pandals"] = [p["id"] for p in pandals
                             if walk_m((p["lat"], p["lng"]), (f["lat"], f["lng"])) / config.DETOUR_FACTOR
                             <= config.NEARBY_FOOD_M]

    # Open data (pipeline.discover): bus stops, routes and autos near each place, plus Commons photos.
    extra = {}
    T = transit_index()
    if T:
        attach_transit(pandals + food, T, _walk_min)
        extra["transit_bundle"] = transit_bundle(T)
    extra["dish_photos"] = attach_photos(pandals, food)
    extra["photo_archive"] = build_archive(pandals)
    extra["awards"] = awards
    extra["panjika"] = load_panjika()
    for f in food:
        f.pop("_archive", None)

    return {**data, **extra, "zones": list(zones.values()), "pandals": pandals}
