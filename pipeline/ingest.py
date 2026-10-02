"""Stage 1: read raw CSVs into typed Python records."""
import csv

from . import config

INT_FIELDS = {"popularity", "crowd_base", "visit_min", "price"}
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
    return {
        name: read_csv(raw_dir / f"{name}.csv")
        for name in ("zones", "pandals", "food", "parking", "transit")
    }
