"""Stage 4: optimal walking order per zone and curated multi-zone itineraries."""
from . import config
from .enrich import crowd_index
from .fitness import kcal_for, steps_for
from .geo import haversine_m, order_route, walk_m

RIDE_KMH = 18          # metro, cab or auto average including waits during puja
RIDE_OVERHEAD_MIN = 10


def _hhmm(minutes):
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _parse(hhmm):
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def _entry_station(transit, pandals):
    """Return the station closest to any pandal in the group."""
    return min(transit, key=lambda t: min(haversine_m((t["lat"], t["lng"]), (p["lat"], p["lng"])) for p in pandals))


def build_route(start, pandals, day_factor=1.0, start_min=18 * 60):
    """Turn a start point and a set of pandals into a timed leg list plus totals."""
    pts = [(p["lat"], p["lng"]) for p in pandals]
    order = order_route((start["lat"], start["lng"]), pts)
    clock, cur = start_min, (start["lat"], start["lng"])
    stops, walk_total, walk_min_total, queue_total = [], 0.0, 0, 0
    for i in order:
        p = pandals[i]
        dist = walk_m(cur, pts[i])
        wmin = round(dist / (config.WALK_KMH_CROWD * 1000 / 60))
        clock += wmin
        crowd = crowd_index(p["crowd_base"], day_factor, clock // 60)
        dwell = round(p["visit_min"] * (0.6 + 0.8 * crowd / 100))
        stops.append({"pandal": p["id"], "walk_m": round(dist), "walk_min": wmin,
                      "arrive": _hhmm(clock), "crowd": crowd, "dwell_min": dwell})
        clock += dwell
        walk_total += dist
        walk_min_total += wmin
        queue_total += dwell
        cur = pts[i]
    return {
        "stops": stops,
        "walk_m": round(walk_total),
        "walk_min": walk_min_total,
        "dwell_min": queue_total,
        "end_min": clock,
    }


def plan(data):
    by_id = {p["id"]: p for p in data["pandals"]}
    transit = {t["id"]: t for t in data["transit"]}
    days = {d["id"]: d for d in config.PUJA_DAYS}

    # A default evening walk for each zone, starting at its entry station.
    for z in data["zones"]:
        members = [by_id[i] for i in z["pandal_ids"]]
        start = _entry_station(data["transit"], members)
        r = build_route(start, members)
        z["route"] = {"start": start["id"], "order": [s["pandal"] for s in r["stops"]],
                      "walk_m": r["walk_m"], "walk_min": r["walk_min"], "dwell_min": r["dwell_min"],
                      "steps": steps_for(r["walk_m"]),
                      "kcal": kcal_for(r["walk_min"], r["dwell_min"])}

    itineraries = []
    for spec in config.CURATED_ITINERARIES:
        day = days[spec["suggested_day"]]
        clock = _parse(spec["suggested_start"])
        start = transit[spec["start"]]
        segments, walk_m_sum, walk_min_sum, dwell_sum, ride_min_sum = [], 0, 0, 0, 0
        last_pt = None
        for zi, zid in enumerate(spec["zones"]):
            members = [p for p in data["pandals"]
                       if p["zone"] == zid and p["popularity"] >= spec["min_popularity"]]
            if not members:
                continue
            seg_start = start if zi == 0 else _entry_station(data["transit"], members)
            if last_pt is not None:
                ride = round(haversine_m(last_pt, (seg_start["lat"], seg_start["lng"])) * 1.25
                             / (RIDE_KMH * 1000 / 60)) + RIDE_OVERHEAD_MIN
                segments.append({"type": "ride", "to_station": seg_start["id"], "ride_min": ride,
                                 "depart": _hhmm(clock)})
                clock += ride
                ride_min_sum += ride
            r = build_route(seg_start, members, day["factor"], clock)
            segments.append({"type": "walk", "zone": zid, "start": seg_start["id"], "stops": r["stops"],
                             "walk_m": r["walk_m"]})
            clock = r["end_min"]
            walk_m_sum += r["walk_m"]
            walk_min_sum += r["walk_min"]
            dwell_sum += r["dwell_min"]
            last_pt = (by_id[r["stops"][-1]["pandal"]]["lat"], by_id[r["stops"][-1]["pandal"]]["lng"])

        n = sum(len(s["stops"]) for s in segments if s["type"] == "walk")
        itineraries.append({
            "id": spec["id"], "name": spec["name"], "name_bn": spec.get("name_bn"),
            "blurb": spec["blurb"], "blurb_bn": spec.get("blurb_bn"), "zones": spec["zones"],
            "day": spec["suggested_day"], "start_time": spec["suggested_start"], "end_time": _hhmm(clock),
            "segments": segments, "pandal_count": n,
            "totals": {
                "walk_km": round(walk_m_sum / 1000, 2), "walk_m": round(walk_m_sum), "walk_min": walk_min_sum, "dwell_min": dwell_sum,
                "ride_min": ride_min_sum, "duration_min": walk_min_sum + dwell_sum + ride_min_sum,
                "steps": steps_for(walk_m_sum), "kcal": kcal_for(walk_min_sum, dwell_sum),
            },
        })
    return {**data, "itineraries": itineraries}
