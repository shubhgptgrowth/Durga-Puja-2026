"""Merge open data from data/discovered/ (written by pipeline.discover) into the guide.

  * Pandals are a one-off, reviewable step that writes rows into data/raw/pandals.csv:
        python -m pipeline.discovered pandals [--dry-run]
  * Transit (bus stops, routes, autos) and photos are attached at build time by
    attach_transit() and attach_photos(), which enrich() calls when the files exist.
"""
import csv
import json
import math
import re
import sys

from . import config
from .audit import similarity
from .geo import haversine_m

DISC = config.ROOT / "data" / "discovered"
SEEDS = config.ROOT / "data" / "seeds" / "pandal_seeds.csv"
# Close enough to stand in for a puja's location (the block centroid, the lake, the locality's bus stop).
APPROX_CLASSES = {"place:neighbourhood", "water:pond", "highway:bus_stop"}
BAD_CLASS = re.compile(r"^(highway|place|boundary|landuse|railway|shop|office):")
PUJA_WORDS = re.compile(r"sarbojan|sarbajan|sarvajan|sarbojaneen|sarbojonin|durgots|durgouts|durga ?puj|durga ?pooj|durga ?utsa|durga ?utsh|puja samiti|puja committee|utshab|utsab|utsav", re.I)
NOT_A_PUJA = re.compile(r"\b(apartment|pharmacy|museum|proposed|jagaddhatri|kali ?puja|steet|st|rd|mandir|temple|math|ashram|school|vidyalaya|college|hospital|road|street|lane|sarani|market|bazar|ghat|kali|shiv|siva|hanuman|jagannath|ram|krishna|radha|shitala|sitala mandir|masjid|church|office|shop|store|bank)\b", re.I)


def _load(name):
    p = DISC / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _zone_centers(zones):
    return {z["id"]: (float(z["lat"]), float(z["lng"])) for z in zones if z.get("lat")}


def nearest_area(pt, centers, region=None, zones=None, max_m=3500):
    cand = [(haversine_m(pt, c), zid) for zid, c in centers.items()
            if region is None or zones.get(zid, {}).get("region") == region]
    cand.sort()
    return cand[0][1] if cand and cand[0][0] <= max_m else None


# ---------------------------------------------------------------- pandals (CSV writer)
def apply_pandals(dry_run=False):
    disc = _load("pandals")
    if not disc:
        sys.exit("data/discovered/pandals.json missing: run the discover workflow first")
    raw = config.RAW_DIR
    rows = list(csv.DictReader(open(raw / "pandals.csv", encoding="utf-8")))
    fields = list(rows[0].keys())
    zones = {z["id"]: z for z in csv.DictReader(open(raw / "zones.csv", encoding="utf-8"))}
    centers = _zone_centers(zones.values())
    have = [(float(r["lat"]), float(r["lng"]), r["name"]) for r in rows]
    ids = {r["id"] for r in rows}
    added, skipped = [], []

    def dup(pt, name):
        return any(haversine_m(pt, (a, b)) < 120 or (haversine_m(pt, (a, b)) < 600 and similarity(name, n) > 0.8) for a, b, n in have)

    def add(row, pt):
        rows.append(row); have.append((pt[0], pt[1], row["name"])); ids.add(row["id"]); added.append(row)

    base = {k: "" for k in fields}
    for s in disc["seeds"]:
        m = s.get("match")
        approx = bool(m) and m.get("class") in APPROX_CLASSES and s["similarity"] >= 0.75
        confident = bool(m) and (s["similarity"] >= 0.85 or (m.get("src") == "nominatim" and s["similarity"] >= 0.75))
        if not m or not confident or (BAD_CLASS.match(m.get("class", "") + ":") and not approx):
            skipped.append((s["id"], f"no confident match ({s['similarity']}, {m and m.get('name')})")); continue
        pt = (m["lat"], m["lng"])
        if dup(pt, s["name"]) or s["id"] in ids:
            skipped.append((s["id"], "already listed")); continue
        region = {"howrah": "howrah", "east": "east", "north": "north", "central": "central", "south": "south"}.get(s["area_hint"])
        zone = nearest_area(pt, centers, region, zones) or nearest_area(pt, centers, None, zones, 6000)
        if not zone:
            skipped.append((s["id"], "outside every area")); continue
        pop = int(s["popularity"])
        add({**base, "id": s["id"], "name": s["name"], "name_bn": s["name_bn"], "zone": zone, "lat": f"{pt[0]:.6f}", "lng": f"{pt[1]:.6f}",
             "geo_source": "osm-approx" if approx else "osm", "tags": "theme" if pop >= 4 else "neighbourhood", "popularity": str(pop), "crowd_base": str(max(2, pop - 1 if pop < 5 else 5)),
             "best_slot": "early_morning" if pop >= 5 else "evening", "visit_min": "20" if pop >= 4 else "15", "est_year": "",
             "highlight": f"A well-known {'theme ' if pop >= 4 else ''}puja in {zones[zone]['short']}. Location from OpenStreetMap.", "verified": "false"}, pt)

    for c in disc["candidates"]:
        name = c["name"].strip()
        if not name or not PUJA_WORDS.search(name) or NOT_A_PUJA.search(name) or BAD_CLASS.match(c.get("class", "") + ":"):
            continue
        pt = (c["lat"], c["lng"])
        first = (re.findall(r"[a-z]{4,}", name.lower()) or [""])[0]
        if dup(pt, name) or any(haversine_m(pt, (a, b)) < 400 and first and first in n.lower() for a, b, n in have):
            continue
        zone = nearest_area(pt, centers, None, zones, 3000)
        if not zone:
            continue
        pid = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:40] or "puja"
        while pid in ids:
            pid += "_2"
        add({**base, "id": pid, "name": re.sub(r"\s+(Durgotsav|Durga Puja|Durgapuja)\s*$", "", name, flags=re.I) or name,
             "name_bn": c.get("name_bn", ""), "zone": zone, "lat": f"{pt[0]:.6f}", "lng": f"{pt[1]:.6f}", "geo_source": "osm-discovered",
             "tags": "neighbourhood", "popularity": "2", "crowd_base": "2", "best_slot": "evening", "visit_min": "15", "est_year": "",
             "highlight": f"A neighbourhood puja in {zones[zone]['short']}, listed on OpenStreetMap.", "verified": "false"}, pt)

    for r in added:
        print(f"ADD  {r['zone']:20} {r['id']:30} pop={r['popularity']} {r['name']}", file=sys.stderr)
    for sid, why in skipped:
        print(f"skip seed {sid:28} {why}", file=sys.stderr)
    print(f"{len(added)} pandals added", file=sys.stderr)
    if not dry_run:
        with open(raw / "pandals.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)


# ---------------------------------------------------------------- transit (build time)
def _seg_dist(p, a, b):
    """Approximate distance (m) from point p to segment a–b, using a local flat projection."""
    k = math.cos(math.radians(p[0])) * 111320
    P, A, B = [(x[1] * k, x[0] * 110540) for x in (p, a, b)]
    dx, dy = B[0] - A[0], B[1] - A[1]
    t = max(0, min(1, ((P[0] - A[0]) * dx + (P[1] - A[1]) * dy) / ((dx * dx + dy * dy) or 1)))
    return math.hypot(P[0] - A[0] - t * dx, P[1] - A[1] - t * dy)


def _route_label(r):
    ref = (r.get("ref") or "").strip()
    return ref if ref else re.sub(r"^(Bus|Auto|Share auto)\s*:?\s*", "", (r.get("name") or "").split(":")[0]).strip()[:24]


def _sort_refs(refs):
    def key(x):
        m = re.match(r"([A-Za-z-]*)(\d+)(.*)", x)
        return (m.group(1), int(m.group(2)), m.group(3)) if m else (x, 0, "")
    return sorted(set(refs), key=key)


def transit_index():
    t = _load("transit")
    if not t:
        return None
    stops = {int(k): v for k, v in t["stops"].items()}
    stop_routes = {}
    for r in t["routes"]:
        lab = _route_label(r)
        if not lab:
            continue
        for sid in r["stops"]:
            stop_routes.setdefault(sid, {"bus": set(), "auto": set()})["auto" if r["mode"] == "share_taxi" else "bus"].add(lab)
    # Curated auto routes: coordinates from the seed file win; geocoded ends fill the gaps.
    seed = {r["id"]: r for r in csv.DictReader(open(config.ROOT / "data" / "seeds" / "auto_routes.csv", encoding="utf-8"))}
    autos = []
    for sid, r in seed.items():
        found = next((a for a in t.get("autos", []) if a["id"] == sid), {"ends": [{}, {}]})
        ends = []
        for i, side in enumerate(("from", "to")):
            if r.get(f"{side}_lat"):
                ends.append({"name": r[side], "lat": float(r[f"{side}_lat"]), "lng": float(r[f"{side}_lng"])})
            elif "lat" in found["ends"][i]:
                ends.append({**found["ends"][i], "name": r[side]})
        if len(ends) == 2:
            autos.append({"id": sid, "note": r["note"], "ends": ends})
    stands = [s for s in t.get("stands", []) if s["kind"] == "taxi"]
    return {"stops": stops, "stop_routes": stop_routes, "autos": autos, "stands": stands, "routes": t["routes"]}


def attach_transit(places, T, walk_min):
    """Adds bus / auto / auto_stands to each place record."""
    for p in places:
        pt = (p["lat"], p["lng"])
        near = sorted((haversine_m(pt, (s["lat"], s["lng"])), sid) for sid, s in T["stops"].items()
                      if abs(s["lat"] - pt[0]) < 0.006 and abs(s["lng"] - pt[1]) < 0.006)
        bus, seen, auto_osm = [], set(), set()
        for d, sid in near:
            if d > 450:
                break
            rs = T["stop_routes"].get(sid)
            if not rs:
                continue
            auto_osm |= rs["auto"]
            name = (T["stops"][sid]["name"] or "").strip() or "Bus stop"
            if not rs["bus"] or name.lower() in seen:
                continue
            seen.add(name.lower())
            bus.append({"stop": name, "distance_m": round(d), "walk_min": walk_min(d), "routes": _sort_refs(rs["bus"])[:12]})
            if len(bus) == 3:
                break
        auto = [{"route": r, "src": "osm"} for r in sorted(auto_osm)][:3]
        for a in T["autos"]:
            e1, e2 = a["ends"]
            d = _seg_dist(pt, (e1["lat"], e1["lng"]), (e2["lat"], e2["lng"]))
            if d <= 600:
                auto.append({"route": f"{e1['name']} ↔ {e2['name']}", "via": a.get("note", ""), "distance_m": round(d), "src": "curated"})
        p["bus"], p["auto"] = bus, auto[:4]
        p["auto_stands"] = [{"name": s["name"] or "Auto / taxi stand", "distance_m": round(haversine_m(pt, (s["lat"], s["lng"])))}
                            for s in sorted(T["stands"], key=lambda s: haversine_m(pt, (s["lat"], s["lng"])))[:2]
                            if haversine_m(pt, (s["lat"], s["lng"])) <= 500]


def transit_bundle(T):
    """Compact transit data for the in-app planner: stops, bus/auto routes and curated autos."""
    used = sorted({sid for r in T["routes"] for sid in r["stops"]})
    pos = {sid: i for i, sid in enumerate(used)}
    return {
        "stops": [[round(T["stops"][s]["lat"], 5), round(T["stops"][s]["lng"], 5), T["stops"][s]["name"]] for s in used],
        "routes": [{"l": _route_label(r), "m": "auto" if r["mode"] == "share_taxi" else "bus", "s": [pos[s] for s in r["stops"] if s in pos]}
                   for r in T["routes"] if _route_label(r)],
        "autos": [{"l": f"{a['ends'][0]['name']} ↔ {a['ends'][1]['name']}", "a": [a["ends"][0]["lat"], a["ends"][0]["lng"]],
                   "b": [a["ends"][1]["lat"], a["ends"][1]["lng"]], "via": a.get("note", "")} for a in T["autos"]],
    }


# ---------------------------------------------------------------- photos (build time)
def _year(ph):
    m = re.search(r"(20\d\d)", f"{ph.get('date', '')} {ph.get('title', '')}")
    return int(m.group(1)) if m else None


def _photo(ph):
    return {"src": ph["thumb"], "page": ph["page"], "author": ph["author"] or "Unknown", "license": ph["license"] or "see source",
            "year": _year(ph), "title": re.sub(r"^File:|\.(jpe?g|png|webp)$", "", ph["title"], flags=re.I)[:90]}


STOP_PH = {"sarbojanin", "sarbojonin", "club", "sangha", "the", "of", "kolkata", "block", "salt", "lake", "puja", "durga", "pally", "sammilani"}
# Other names a puja is known by on Commons.
PHOTO_ALIASES = {"tala_prattoy": ["Tala Baroari", "Tala Barowari"], "maddox_square": ["Ballygunge Durga Puja Samiti"],
                 "deshapriya_park": ["Ballygunge Sarbojanin Durgotsab"]}


def _words(s):
    return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP_PH and len(w) > 2]


def _strict(name, text, shared_first):
    """The first distinctive word must appear. When that word is shared by several places
    (Behala, Kalighat, Dum Dum...), a second distinctive word must appear too."""
    words, have = _words(name), set(_words(text))
    if not words or words[0] not in have:
        return False
    return words[0] not in shared_first or sum(w in have for w in words) >= min(2, len(words))


def attach_photos(pandals, food):
    ph = _load("photos")
    if not ph:
        return {}
    block = {"dish": set(), "place": set(), "title": set()}
    bl = config.RAW_DIR / "photo_blocklist.csv"
    if bl.exists():
        for r in csv.DictReader(open(bl, encoding="utf-8")):
            block.setdefault(r["kind"], set()).add(r["value"])
    places = {p["id"]: p for p in pandals + food}
    firsts = {}
    for p in places.values():
        w = _words(p["name"])
        if w:
            firsts[w[0]] = firsts.get(w[0], 0) + 1
    shared_first = {w for w, n in firsts.items() if n > 1}
    # A photo can match several similar names (Kumartuli Park vs Kumartuli Sarbojanin):
    # it goes only to the place whose full name matches its title best.
    owner = {}
    for pid, items in ph["places"].items():
        p = places.get(pid)
        if not p or pid in block["place"]:
            continue
        for x in items:
            text = f"{x['title']} {x.get('desc', '')}"
            names = [p["name"], *PHOTO_ALIASES.get(pid, [])]
            if x["title"] in block["title"] or any(k in x["title"] for k in block.get("title_contains", ())) or not any(_strict(n, text, shared_first) for n in names):
                continue
            score = max(similarity(n, re.sub(r"\d+|\.\w+$", "", x["title"])) for n in names)
            if x["page"] not in owner or score > owner[x["page"]][0]:
                owner[x["page"]] = (score, pid, x)
    per = {}
    for score, pid, x in owner.values():
        per.setdefault(pid, []).append(x)
    for p in pandals + food:
        items = sorted(per.get(p["id"], []), key=lambda x: -(_year(x) or 0))
        p["photos"] = [_photo(x) for x in items[:6]]
    return {d: _photo(v[0]) for d, v in ph.get("dishes", {}).items() if v and d not in block["dish"]}


if __name__ == "__main__":
    if sys.argv[1:2] == ["pandals"]:
        apply_pandals(dry_run="--dry-run" in sys.argv)
