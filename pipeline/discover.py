"""Discover data from open sources (needs internet, so it runs in the `discover` workflow).

    python -m pipeline.discover pandals   # OSM pujas + matches for data/seeds/pandal_seeds.csv
    python -m pipeline.discover transit   # OSM bus/share-auto routes and stops, taxi/auto stands, auto-route endpoints
    python -m pipeline.discover photos    # Wikimedia Commons photos for pandals, eateries and signature dishes

Each command writes data/discovered/<name>.json. Nothing goes into the app until
`python -m pipeline` merges it with the review rules in pipeline/merge_discovered.py.
"""
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request

from . import config
from .audit import UA, search as nominatim, similarity
from .geo import haversine_m
from .ingest import ingest

OUT = config.ROOT / "data" / "discovered"
OVERPASS = "https://overpass-api.de/api/interpreter"
COMMONS = "https://commons.wikimedia.org/w/api.php"
BB = config.BBOX
BBOX_Q = f'{BB["lat_min"]},{BB["lng_min"]},{BB["lat_max"]},{BB["lng_max"]}'


MIRRORS = [OVERPASS, "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"]


def overpass(q, timeout=180):
    """POST to Overpass, retrying across public mirrors (they 429/504 under load)."""
    last = None
    for attempt in range(6):
        url = MIRRORS[attempt % len(MIRRORS)]
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": q}).encode(), headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout + 30) as r:
                return json.load(r)["elements"]
        except Exception as e:  # 429 / 504 / timeouts
            last = e
            print(f"overpass {url} failed ({e}); retrying", file=sys.stderr)
            time.sleep(15 * (attempt + 1))
    raise last


def center(e):
    if "lat" in e:
        return e["lat"], e["lon"]
    c = e.get("center") or {}
    return c.get("lat"), c.get("lon")


def write(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote data/discovered/{name}.json", file=sys.stderr)


# ---------------------------------------------------------------- pandals
PUJA_RE = "[Dd]urg|[Pp]uj|[Pp]ooj|[Ss]arbojan|[Ss]arbajan|[Ss]arvajan|[Dd]urgotsa|পুজো|পূজা|দুর্গ|সার্বজনীন"


def discover_pandals():
    q = (f'[out:json][timeout:180];(nwr["name"~"{PUJA_RE}"]({BBOX_Q});nwr["name:bn"~"পুজো|পূজা|দুর্গ|সার্বজনীন"]({BBOX_Q}););out center tags;')
    els = overpass(q)
    cands = []
    for e in els:
        tags = e.get("tags", {})
        lat, lng = center(e)
        if lat is None:
            continue
        name = tags.get("name:en") or tags.get("name", "")
        if re.search(r"\b(school|college|hospital|road|street|lane|sarani|market|bazar|ghat|station|temple|mandir|math|ashram)\b", name, re.I) and not re.search(PUJA_RE, name):
            continue
        cands.append({"osm": f"{e['type']}/{e['id']}", "name": name, "name_bn": tags.get("name:bn", ""), "lat": round(lat, 6), "lng": round(lng, 6),
                      "class": f"{next((k for k in ('amenity', 'tourism', 'leisure', 'historic', 'building') if k in tags), '')}:{tags.get('amenity') or tags.get('tourism') or tags.get('leisure') or ''}"})
    print(f"overpass: {len(cands)} puja-like features", file=sys.stderr)

    seeds = list(csv.DictReader(open(config.ROOT / "data" / "seeds" / "pandal_seeds.csv", encoding="utf-8")))
    matches = []
    for s in seeds:
        hits = []
        for q in (f"{s['query']}, Kolkata", s["query"], f"{s['name']} Durgotsav", s["name"]):
            try:
                hits += nominatim(q)
            except Exception as ex:  # keep going on hiccups
                print("nominatim error", ex, file=sys.stderr)
            time.sleep(1.1)
            if hits and max(similarity(s["name"], h.get("name") or "") for h in hits) >= 0.8:
                break
        # Overpass candidates count too, so a mapped puja wins even if Nominatim misses it.
        pool = [{"name": h.get("name") or "", "lat": float(h["lat"]), "lng": float(h["lon"]),
                 "class": f"{h.get('category', '')}:{h.get('type', '')}", "src": "nominatim"} for h in hits]
        pool += [{**c, "src": "overpass"} for c in cands]
        best = max(pool, key=lambda h: similarity(s["name"], h["name"]), default=None)
        row = {**s, "match": best, "similarity": round(similarity(s["name"], best["name"]), 2) if best else 0}
        matches.append(row)
        print(f"seed {s['id']:28} sim={row['similarity']:.2f} {best['name'] if best else '-'}", file=sys.stderr)
    write("pandals", {"candidates": cands, "seeds": matches})


# ---------------------------------------------------------------- transit
def discover_transit():
    q = (f'[out:json][timeout:240];(relation["route"~"^(bus|share_taxi|minibus)$"]({BBOX_Q}););out body;'
         f'node(r:"stop");out;node(r:"platform");out;node(r:"stop_entry_only");out;node(r:"stop_exit_only");out;')
    els = overpass(q, 240)
    rels = [e for e in els if e["type"] == "relation"]
    nodes = {e["id"]: e for e in els if e["type"] == "node"}
    routes = []
    for r in rels:
        t = r.get("tags", {})
        stop_ids = [m["ref"] for m in r.get("members", []) if m["type"] == "node" and m["ref"] in nodes]
        if len(stop_ids) < 2:
            continue
        routes.append({"id": r["id"], "mode": t.get("route"), "ref": t.get("ref", ""), "name": t.get("name:en") or t.get("name", ""),
                       "from": t.get("from", ""), "to": t.get("to", ""), "operator": t.get("operator", ""), "stops": stop_ids})
    used = {i for r in routes for i in r["stops"]}
    stops = {i: {"name": nodes[i].get("tags", {}).get("name:en") or nodes[i].get("tags", {}).get("name", ""),
                 "lat": round(nodes[i]["lat"], 6), "lng": round(nodes[i]["lon"], 6)} for i in used}
    print(f"overpass: {len(routes)} routes, {len(stops)} stops", file=sys.stderr)

    stands = overpass(f'[out:json][timeout:60];(nwr["amenity"="taxi"]({BBOX_Q});nwr["amenity"="bus_station"]({BBOX_Q}););out center tags;')
    stands = [{"name": e.get("tags", {}).get("name", ""), "kind": e["tags"].get("amenity"), "lat": round(center(e)[0], 6), "lng": round(center(e)[1], 6),
               "taxi": e["tags"].get("taxi", ""), "auto": e["tags"].get("auto_rickshaw", "")} for e in stands if center(e)[0]]
    print(f"overpass: {len(stands)} taxi/auto/bus stands", file=sys.stderr)

    autos = []
    for a in csv.DictReader(open(config.ROOT / "data" / "seeds" / "auto_routes.csv", encoding="utf-8")):
        ends = []
        for place in (a["from"], a["to"]):
            try:
                hits = nominatim(f"{place}, Kolkata")
            except Exception:
                hits = []
            time.sleep(1.1)
            h = hits[0] if hits else None
            ends.append({"name": place, "lat": round(float(h["lat"]), 6), "lng": round(float(h["lon"]), 6), "osm_name": h.get("name", "")} if h else {"name": place})
        autos.append({**a, "ends": ends})
        print(f"auto {a['id']:24} {[e.get('osm_name', '?') for e in ends]}", file=sys.stderr)
    write("transit", {"routes": routes, "stops": stops, "stands": stands, "autos": autos})


# ---------------------------------------------------------------- photos (Wikimedia Commons)
STOP = {"sarbojanin", "sarbojonin", "club", "sangha", "the", "of", "kolkata", "block", "salt", "lake", "park", "puja", "durga", "pally", "sammilani"}


def _tokens(s):
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 2}


def _matches(name, text):
    """The first distinctive word of the name must appear, plus at least half of the rest."""
    words = [w for w in re.findall(r"[a-z0-9]+", name.lower()) if w not in STOP and len(w) > 2]
    if not words:
        return False
    have = _tokens(text)
    return words[0] in have and sum(w in have for w in words) >= max(1, (len(words) + 1) // 2)


def commons(q, limit=12):
    p = {"action": "query", "format": "json", "generator": "search", "gsrsearch": f"{q} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": limit,
         "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 720}
    req = urllib.request.Request(f"{COMMONS}?{urllib.parse.urlencode(p)}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        pages = (json.load(r).get("query") or {}).get("pages", {})
    out = []
    for pg in sorted(pages.values(), key=lambda x: x.get("index", 99)):
        ii = (pg.get("imageinfo") or [{}])[0]
        md = ii.get("extmetadata", {})
        val = lambda k: re.sub(r"<[^>]+>", "", (md.get(k) or {}).get("value", "")).strip()
        out.append({"title": pg["title"], "thumb": ii.get("thumburl"), "url": ii.get("url"), "page": ii.get("descriptionurl"),
                    "w": ii.get("thumbwidth"), "h": ii.get("thumbheight"), "author": val("Artist")[:80], "license": val("LicenseShortName"),
                    "license_url": val("LicenseUrl"), "date": val("DateTimeOriginal")[:10], "desc": val("ImageDescription")[:160]})
    return out


def discover_photos():
    data = ingest()
    seeds = list(csv.DictReader(open(config.ROOT / "data" / "seeds" / "pandal_seeds.csv", encoding="utf-8")))
    places = [("pandal", p["id"], p["name"]) for p in data["pandals"]] + [("pandal", s["id"], s["name"]) for s in seeds]
    places += [("food", f["id"], f["name"].split("(")[0].strip()) for f in data["food"] if f["type"] != "street"]
    res = {"places": {}, "dishes": {}}
    for kind, pid, name in places:
        words = [w for w in re.findall(r"[a-z0-9]+", name.lower()) if w not in STOP and len(w) > 2]
        qs = [f"{name} durga puja", f"{words[0]} durga puja pandal"] if kind == "pandal" and words else [f"{name} Kolkata"]
        try:
            hits = []
            for q in qs:
                hits += commons(q); time.sleep(0.4)
        except Exception as ex:
            print("commons error", pid, ex, file=sys.stderr); hits = []
        keep = []
        for h in hits:
            text = f"{h['title']} {h['desc']}".lower()
            if _matches(name, text) and h["thumb"] and h["url"] not in {k["url"] for k in keep}:
                keep.append(h)
        res["places"][pid] = keep[:8]
        print(f"photos {pid:28} {len(keep)} / {len(hits)}", file=sys.stderr)
        time.sleep(0.4)
    dishes = sorted({d for f in data["food"] for d in f["dishes"]})
    for d in dishes:
        try:
            hits = commons(f"{d} Bengali food", 8) or commons(d, 8)
        except Exception:
            hits = []
        need = _tokens(d)
        keep = [h for h in hits if need and need & _tokens(h["title"] + " " + h["desc"]) and h["thumb"]][:2]
        res["dishes"][d] = keep
        print(f"dish   {d:28} {len(keep)}", file=sys.stderr)
        time.sleep(0.4)
    write("photos", res)


if __name__ == "__main__":
    {"pandals": discover_pandals, "transit": discover_transit, "photos": discover_photos}[sys.argv[1]]()
