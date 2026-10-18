"""Move pandal pins to where independent evidence says the pandal is (data/discovered/pins.json, written by
`python -m pipeline.discover pins`). A reviewable step, like pipeline.discovered:

    python -m pipeline.pins [--dry-run]

Evidence, strongest first:
  * google: the pandal's own Google Maps listing (data/discovered/google.json, `discover google`), when its name
    matches the pandal and it lies within 4 km of the pandal's area. Its place id is kept so Directions open that
    exact listing.
  * photos: camera locations of Commons photos that name the pandal. Two or more within 200 m of each other make a
    cluster; its median is the pin. One stray photo (taken at Kumartuli, or of a replica) never moves a pin.
  * landmark: the park or square the puja is named after (Maddox Square, Deshapriya Park), from OpenStreetMap.
When both exist they must agree (within 350 m), else the pandal is listed for a person to check and left alone.
Pins that are already close (under 100 m) stay put, and a move of more than 5 km is listed, never applied.
"""
import csv
import json
import re
import statistics
import sys

from . import config
from .geo import haversine_m

PINS = config.ROOT / "data" / "discovered" / "pins.json"
GOOGLE = config.ROOT / "data" / "discovered" / "google.json"
ZONE_M = 4000
CLUSTER_M, AGREE_M, KEEP_M, MAX_MOVE_M = 200, 350, 100, 5000


def photo_cluster(shots):
    """The largest group of photo locations within CLUSTER_M of one of them, if it has two or more."""
    pts = [(s["lat"], s["lng"]) for s in shots]
    best = []
    for a in pts:
        near = [b for b in pts if haversine_m(a, b) <= CLUSTER_M]
        if len(near) > len(best):
            best = near
    if len(best) < 2:
        return None
    return (statistics.median(p[0] for p in best), statistics.median(p[1] for p in best)), len(best)


def google_pick(row, listings, zone):
    """The best-named Google listing for this pandal near its area, or None."""
    from .discover import _matches
    from .audit import similarity
    best = None
    for x in listings or []:
        if haversine_m((x["lat"], x["lng"]), (float(zone["lat"]), float(zone["lng"]))) > ZONE_M:
            continue
        sim = similarity(row["name"], x["name"])
        if (_matches(row["name"], x["name"]) or sim >= 0.75) and (not best or sim > best[0]):
            best = (sim, x)
    return best[1] if best else None


def decide(ev, g=None):
    """(new point, source, note) or (None, None, reason)."""
    if g:
        return (g["lat"], g["lng"]), "google", f"Google Maps: {g['name']}"
    cl = photo_cluster(ev.get("photos") or [])
    mark = ev.get("landmark")
    mk = (mark["lat"], mark["lng"]) if mark else None
    if cl and mk and haversine_m(cl[0], mk) > AGREE_M:
        return None, None, f"photos and {mark['name']} disagree by {haversine_m(cl[0], mk):.0f} m"
    if cl:
        return cl[0], "commons-geotag", f"{cl[1]} photo locations"
    if mk:
        return mk, "osm-landmark", f"{mark['name']} ({mark['kind']})"
    return None, None, "no evidence"


def apply_pins(dry_run=False):
    if not PINS.exists() and not GOOGLE.exists():
        sys.exit("no evidence yet: run the discover workflow with what=pins (and what=google once the key is set)")
    ev = json.loads(PINS.read_text(encoding="utf-8"))["pandals"] if PINS.exists() else {}
    goog = json.loads(GOOGLE.read_text(encoding="utf-8"))["pandals"] if GOOGLE.exists() else {}
    zones = {z["id"]: z for z in csv.DictReader(open(config.RAW_DIR / "zones.csv", encoding="utf-8"))}
    path = config.RAW_DIR / "pandals.csv"
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    fields = list(rows[0].keys()) + [f for f in ("gplace",) if f not in rows[0]]
    moved, flagged, kept, none = [], [], 0, 0
    for r in rows:
        e = ev.get(r["id"]) or {}
        if r.get("verified", "").lower() == "true":
            continue
        g = google_pick(r, goog.get(r["id"]), zones[r["zone"]])
        if g:
            r["gplace"] = g["place_id"]
        pt, src, note = decide(e, g)
        if not pt:
            none += note == "no evidence"
            if note != "no evidence":
                flagged.append((r["id"], note))
            continue
        d = haversine_m((float(r["lat"]), float(r["lng"])), pt)
        if d < KEEP_M:
            kept += 1
            if src == "google" and r["geo_source"] != "google":
                r["geo_source"] = "google"   # confirmed, even if it barely moved
            continue
        if d > MAX_MOVE_M:
            flagged.append((r["id"], f"{src} says {d / 1000:.1f} km away ({note}); not moved"))
            continue
        moved.append((r["id"], d, src, note))
        r["lat"], r["lng"], r["geo_source"] = f"{pt[0]:.6f}", f"{pt[1]:.6f}", src
        r["highlight"] = re.sub(r"\s*Pin is approximate[^.]*\.?\s*ask locally for the exact lane\.", "", r["highlight"]).strip()
    for pid, d, src, note in sorted(moved, key=lambda x: -x[1]):
        print(f"MOVE {pid:30} {d:6.0f} m  {src:15} {note}", file=sys.stderr)
    for pid, why in flagged:
        print(f"CHECK {pid:29} {why}", file=sys.stderr)
    print(f"{len(moved)} moved, {kept} already within {KEEP_M} m, {len(flagged)} to check by hand, {none} without evidence",
          file=sys.stderr)
    if not dry_run:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    apply_pins(dry_run="--dry-run" in sys.argv)
