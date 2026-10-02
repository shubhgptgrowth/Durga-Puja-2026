"""Coordinate audit against OpenStreetMap (Nominatim).

    python -m pipeline.audit [--out data/audit/geo_audit.csv] [--only pandals,food]

For every record it searches OSM for the record's name inside the Kolkata bounding
box, picks the best name match, and reports how far our coordinate is from OSM's.
It needs internet access, so it runs in the `geo-audit` GitHub workflow rather
than in the build. It obeys Nominatim's usage policy: one request per second and
an identifying User-Agent.

Rows with a `geo_query` column use that string instead of the name. Use it for
pandals named after a park or street, for example "Mohammad Ali Park, Kolkata".
"""
import argparse
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

from . import config
from .geo import haversine_m
from .ingest import ingest

UA = "PujoParikrama/1.0 (+https://github.com/shubhgptgrowth/Durga-Puja-2026)"
ENDPOINT = "https://nominatim.openstreetmap.org/search"
STOPWORDS = {"sarbojanin", "sarbojanin,", "club", "sangha", "the", "of", "kolkata", "salt", "lake", "(suburban)", "metro"}


def _norm(s):
    return " ".join(w for w in s.lower().replace("(", " ").replace(")", " ").replace(",", " ").split() if w not in STOPWORDS)


def similarity(a, b):
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


# Pandals named after a park, square or street: search for the place itself.
ALIASES = {
    "md_ali_park": "Mohammad Ali Park", "college_square": "College Square", "santosh_mitra": "Santosh Mitra Square",
    "deshapriya_park": "Deshapriya Park", "singhi_park": "Singhi Park", "maddox_square": "Maddox Square",
    "jagat_mukherjee": "Jagat Mukherjee Park", "hindustan_park": "Hindustan Park", "ekdalia": "Ekdalia Road",
    "jodhpur_park": "Jodhpur Park", "fd_block": "FD Block, Sector III, Bidhannagar", "bj_block": "BJ Block, Bidhannagar",
    "ae_block": "AE Block, Bidhannagar", "kumartuli_park": "Kumartuli Park", "kashi_bose_lane": "Kashi Bose Lane",
    "nalin_sarkar": "Nalin Sarkar Street", "bosepukur_sitala": "Bosepukur", "66_pally": "Kalighat Road",
    "sovabazar_rajbari": "Shobhabazar Rajbari", "lake_mall": "Lake Mall", "city_centre_parking": "City Centre Salt Lake",
    "city_centre_food": "City Centre Salt Lake", "south_city": "South City Mall", "quest_mall": "Quest Mall",
    "forum_mall": "Forum Mall Elgin Road", "diamond_plaza": "Diamond Plaza Jessore Road",
}


def query_for(kind, row):
    if row.get("geo_query"):
        return row["geo_query"]
    if row["id"] in ALIASES:
        return ALIASES[row["id"]] + ", Kolkata"
    name = row["name"]
    if kind == "transit":
        return f"{name} metro station, Kolkata" if row.get("line") != "suburban" else f"{name.split('(')[0].strip()} railway station, Kolkata"
    return f"{name}, Kolkata"


def search(q):
    bb = config.BBOX
    params = urllib.parse.urlencode({
        "q": q, "format": "jsonv2", "limit": 5, "bounded": 1, "accept-language": "en",
        "viewbox": f"{bb['lng_min']},{bb['lat_max']},{bb['lng_max']},{bb['lat_min']}",
    })
    req = urllib.request.Request(f"{ENDPOINT}?{params}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def audit(kinds, sleep=1.1):
    data = ingest()
    rows = []
    for kind in kinds:
        for rec in data[kind]:
            q = query_for(kind, rec)
            try:
                hits = search(q)
            except Exception as e:  # network hiccup: record it and move on
                hits, err = [], str(e)
            else:
                err = ""
            best = max(hits, key=lambda h: similarity(rec["name"], h.get("name") or h.get("display_name", "")), default=None)
            row = {"kind": kind, "id": rec["id"], "name": rec["name"], "query": q,
                   "our_lat": rec["lat"], "our_lng": rec["lng"], "osm_name": "", "osm_class": "",
                   "osm_lat": "", "osm_lng": "", "distance_m": "", "similarity": "", "error": err}
            if best:
                lat, lng = float(best["lat"]), float(best["lon"])
                row.update(osm_name=best.get("name") or best.get("display_name", "")[:60],
                           osm_class=f"{best.get('category', best.get('class', ''))}:{best.get('type', '')}",
                           osm_lat=round(lat, 6), osm_lng=round(lng, 6),
                           distance_m=round(haversine_m((rec["lat"], rec["lng"]), (lat, lng))),
                           similarity=round(similarity(rec["name"], best.get("name") or ""), 2))
            rows.append(row)
            print(f"{kind:8} {rec['id']:28} d={row['distance_m'] or '-':>6} sim={row['similarity'] or '-':>4}  {row['osm_name']}", flush=True)
            time.sleep(sleep)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(config.ROOT / "data" / "audit" / "geo_audit.csv"))
    ap.add_argument("--only", default="transit,parking,food,pandals")
    args = ap.parse_args()
    rows = audit(args.only.split(","))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    found = [r for r in rows if r["distance_m"] != ""]
    far = [r for r in found if r["distance_m"] > 150 and r["similarity"] >= 0.6]
    print(f"\n{len(found)}/{len(rows)} matched in OSM; {len(far)} good name matches are >150 m from our pin", file=sys.stderr)


if __name__ == "__main__":
    main()
