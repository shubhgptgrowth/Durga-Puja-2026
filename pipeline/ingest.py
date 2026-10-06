"""Stage 1: read raw CSVs into typed Python records."""
import csv

from . import config

INT_FIELDS = {"popularity", "crowd_base", "visit_min", "price", "cost2"}
FLOAT_FIELDS = {"lat", "lng"}
LIST_FIELDS = {"tags", "dishes"}
BOOL_FIELDS = {"verified"}


def _coerce(field, value):
    value = (value or "").strip()
    if field in FLOAT_FIELDS:
        return float(value) if value else None
    if field in INT_FIELDS:
        return int(value) if value else None
    if field in LIST_FIELDS:
        return [v.strip() for v in value.split("|") if v.strip()]
    if field in BOOL_FIELDS:
        return value.lower() in {"true", "1", "yes", "y"}
    if field == "est_year":
        return int(value) if value else None
    return value


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return [{k: _coerce(k, v) for k, v in row.items()} for row in csv.DictReader(fh)]


def ingest(raw_dir=config.RAW_DIR):
    data = {
        name: read_csv(raw_dir / f"{name}.csv")
        for name in ("regions", "zones", "pandals", "food", "parking", "transit")
    }
    # This year's themes, one row per pandal with its source; filled in as committees announce them (from Mahalaya).
    themes = raw_dir / f"themes_{config.YEAR}.csv"
    data["themes"] = read_csv(themes) if themes.exists() else []
    return data
