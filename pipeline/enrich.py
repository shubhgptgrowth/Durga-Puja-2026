"""Stage 3: derive zone geometry, nearest metro/parking/food, and crowd windows."""
from . import config
from .discovered import attach_photos, attach_transit, build_archive, transit_bundle, transit_index
from .geo import centroid, haversine_m, walk_m

THEMES = config.RAW_DIR / "themes_2026.csv"


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
    for f in food:
        f.pop("_archive", None)

    return {**data, **extra, "zones": list(zones.values()), "pandals": pandals}
