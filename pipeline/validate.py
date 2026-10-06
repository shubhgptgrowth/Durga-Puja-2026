"""Stage 2: schema and integrity checks. Errors stop the build; warnings get reported."""
import re

from . import config
from .geo import haversine_m

REQUIRED = {
    "regions": ["id", "name", "name_bn", "color"],
    "zones": ["id", "region", "name", "color"],
    "pandals": ["id", "name", "zone", "lat", "lng", "popularity", "crowd_base", "best_slot", "visit_min"],
    "food": ["id", "name", "zone", "lat", "lng", "type", "dishes", "veg", "price"],
    "parking": ["id", "name", "zone", "lat", "lng", "kind"],
    "transit": ["id", "name", "line", "lat", "lng"],
    "themes": ["id", "theme", "source_url", "source_name"],   # source_date when the report has one
}
THEME_MAX = 100   # one line on a pandal sheet
VEG_VALUES = {"veg", "nonveg", "both"}
CAR_ADVISORY = {"ok", "limited", "avoid"}


class ValidationError(Exception):
    def __init__(self, errors):
        super().__init__("\n".join(errors))
        self.errors = errors


def validate(data):
    errors, warnings = [], []
    zone_ids = {z["id"] for z in data["zones"]}
    bb = config.BBOX

    for kind, rows in data.items():
        seen = set()
        for i, row in enumerate(rows):
            where = f"{kind}[{i}] ({row.get('id') or '?'})"
            for f in REQUIRED[kind]:
                if row.get(f) in (None, "", []):
                    errors.append(f"{where}: missing required field '{f}'")
            rid = row.get("id")
            if rid in seen:
                errors.append(f"{where}: duplicate id")
            seen.add(rid)
            if "lat" in row and row.get("lat") is not None:
                if not (bb["lat_min"] <= row["lat"] <= bb["lat_max"] and bb["lng_min"] <= row["lng"] <= bb["lng_max"]):
                    errors.append(f"{where}: coordinates {row['lat']},{row['lng']} are outside Kolkata")
            if kind not in ("regions", "zones", "transit", "themes") and row.get("zone") not in zone_ids:
                errors.append(f"{where}: unknown zone '{row.get('zone')}'")
            if kind in ("zones", "pandals", "regions") and not row.get("name_bn") and row.get("geo_source") != "osm-discovered":
                warnings.append(f"{where}: missing Bengali name (name_bn)")
            if "verified" in row and not row["verified"]:
                warnings.append(f"{where}: coordinates not ground-verified")

    region_ids = {r["id"] for r in data["regions"]}
    for z in data["zones"]:
        if z.get("region") not in region_ids:
            errors.append(f"zones ({z['id']}): unknown region '{z.get('region')}'")
        if z.get("car_advisory") not in CAR_ADVISORY:
            errors.append(f"zones ({z['id']}): car_advisory must be one of {sorted(CAR_ADVISORY)}")

    # Themes are published facts about a committee's pujo, so each one needs its source.
    pandal_ids = {p["id"] for p in data["pandals"]}
    for th in data.get("themes", []):
        where = f"themes ({th.get('id')})"
        if th.get("id") not in pandal_ids:
            errors.append(f"{where}: no pandal with this id")
        if not str(th.get("source_url", "")).startswith("https://"):
            errors.append(f"{where}: source_url must be an https:// link")
        if len(th.get("theme") or "") > THEME_MAX:
            errors.append(f"{where}: theme is longer than {THEME_MAX} characters")
        if th.get("source_date") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", th["source_date"]):
            errors.append(f"{where}: source_date must be YYYY-MM-DD (or empty when the report gives no date)")

    for p in data["pandals"]:
        if p.get("best_slot") not in config.SLOTS:
            errors.append(f"pandals ({p['id']}): best_slot '{p.get('best_slot')}' is not one of {list(config.SLOTS)}")
        for f in ("popularity", "crowd_base"):
            if p.get(f) is not None and not 1 <= p[f] <= 5:
                errors.append(f"pandals ({p['id']}): {f} must be between 1 and 5")

    for f in data["food"]:
        if f.get("veg") not in VEG_VALUES:
            errors.append(f"food ({f['id']}): veg must be one of {sorted(VEG_VALUES)}")
        if f.get("price") is not None and not 1 <= f["price"] <= 3:
            errors.append(f"food ({f['id']}): price must be between 1 and 3")

    # Two pandals almost on top of each other usually means a copy-paste error.
    pandals = data["pandals"]
    for i in range(len(pandals)):
        for j in range(i + 1, len(pandals)):
            a, b = pandals[i], pandals[j]
            if haversine_m((a["lat"], a["lng"]), (b["lat"], b["lng"])) < 25:
                warnings.append(f"pandals {a['id']} and {b['id']} are less than 25 m apart. Check the coordinates.")

    zone_counts = {z: 0 for z in zone_ids}
    for p in pandals:
        if p.get("zone") in zone_counts:
            zone_counts[p["zone"]] += 1
    for z, c in zone_counts.items():
        if c == 0:
            warnings.append(f"zones ({z}): has no pandals yet, so it is left out of the bundle")

    for it in config.CURATED_ITINERARIES:
        for z in it["zones"]:
            if z not in zone_ids:
                errors.append(f"itinerary {it['id']}: unknown zone '{z}'")
        if it["start"] not in {t["id"] for t in data["transit"]}:
            errors.append(f"itinerary {it['id']}: unknown start station '{it['start']}'")

    if errors:
        raise ValidationError(errors)
    return warnings
