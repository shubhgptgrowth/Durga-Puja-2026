"""Run the full pipeline: python -m pipeline [--check]"""
import argparse
import sys
import time

from . import config
from .emit import emit
from .enrich import enrich
from .ingest import ingest
from .plan import plan
from .validate import ValidationError, validate


def run(raw_dir=config.RAW_DIR, out_dir=config.OUT_DIR, check_only=False):
    t0 = time.perf_counter()
    data = ingest(raw_dir)
    print(f"[1/5] ingest    {', '.join(f'{k}={len(v)}' for k, v in data.items())}")
    warnings = validate(data)
    print(f"[2/5] validate  OK ({len(warnings)} warnings)")
    if check_only:
        return None
    data = enrich(data)
    print("[3/5] enrich    nearest metro, parking and food, plus crowd windows")
    data = plan(data)
    print(f"[4/5] plan      {len(data['zones'])} zone routes, {len(data['itineraries'])} itineraries")
    bundle = emit(data, warnings, out_dir)
    print(f"[5/5] emit      {out_dir}/guide.json v{bundle['meta']['version']} in {time.perf_counter() - t0:.2f}s")
    return bundle


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="validate only, don't write output")
    args = ap.parse_args()
    try:
        run(check_only=args.check)
    except ValidationError as e:
        print("Validation failed:\n  - " + "\n  - ".join(e.errors), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
