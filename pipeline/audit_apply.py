"""Apply confident OpenStreetMap corrections from a geo audit to data/raw.

    python -m pipeline.audit_apply data/audit/geo_audit.json [--dry-run]

A match is applied only when all of these hold:
  * the OSM feature is the right *kind* of thing (a station for transit, a puja,
    place of worship, park or attraction for pandals, a restaurant or cafe for
    food, a mall for parking), never a road or neighbourhood centroid;
  * the names agree: similarity >= 0.59, or every OSM name word appears in our name;
  * the correction is under MAX_MOVE_M (anything further is probably another branch).
Applied rows get geo_source=osm. Everything else is left for a human to review.
"""
import argparse
import csv
import json
import sys

from . import config

MAX_MOVE_M = 2000
MIN_MOVE_M = 15
OK_CLASSES = {
    "transit": {"railway:subway", "railway:station", "railway:halt"},
    "pandals": {"amenity:place_of_worship", "tourism:attraction", "leisure:park", "leisure:pitch", "tourism:museum", "historic:building"},
    "food": {"amenity:restaurant", "amenity:cafe", "amenity:fast_food", "shop:confectionery", "shop:pastry"},
    "parking": {"shop:mall", "shop:supermarket", "amenity:parking", "building:retail"},
}
STOP = {"the", "of", "kolkata", "restaurant", "durgotsav", "durga", "puja"}


def _words(s):
    return {w for w in s.lower().replace("(", " ").replace(")", " ").replace(",", " ").replace("'", "").split() if w not in STOP}


def accept(r):
    if r["distance_m"] in ("", None) or not r["osm_class"]:
        return False, "no match"
    if r["osm_class"] not in OK_CLASSES[r["kind"]]:
        return False, f"class {r['osm_class']}"
    if r["distance_m"] > MAX_MOVE_M:
        return False, f"{r['distance_m']} m: probably another branch"
    osm_words = _words(r["osm_name"])
    if not (r["similarity"] >= 0.59 or (osm_words and osm_words <= _words(r["name"]))):
        return False, f"name {r['osm_name']!r}"
    return True, "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audit")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    rows = json.load(open(args.audit, encoding="utf-8"))
    by_kind = {}
    for r in rows:
        ok, why = accept(r)
        by_kind.setdefault(r["kind"], {})[r["id"]] = (ok, why, r)
    for kind, recs in by_kind.items():
        path = config.RAW_DIR / f"{kind}.csv"
        data = list(csv.DictReader(open(path, encoding="utf-8")))
        fields = list(data[0].keys())
        if "geo_source" not in fields:
            fields.insert(fields.index("lng") + 1, "geo_source")
        moved = 0
        for row in data:
            row.setdefault("geo_source", row.get("geo_source") or "curated")
            ok, why, r = recs.get(row["id"], (False, "not audited", None))
            if ok and r["distance_m"] >= MIN_MOVE_M:
                row["lat"], row["lng"] = f"{r['osm_lat']:.6f}", f"{r['osm_lng']:.6f}"
                moved += 1
            if ok:
                row["geo_source"] = "osm"
            print(f"{'APPLY' if ok else 'skip ':5} {kind:8} {row['id']:26} {why}", file=sys.stderr)
        if not args.dry_run:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader(); w.writerows(data)
        print(f"{kind}: {moved} moved, {sum(1 for o, _, _ in recs.values() if o)} confirmed via OSM", file=sys.stderr)


if __name__ == "__main__":
    main()
