"""Post a hand-picked batch of reels and carousels to Instagram, spaced out, through the Graph API.

    IG_USER_ID=… IG_ACCESS_TOKEN=… python -m marketing.publish_batch marketing/batches/2026-10-04.json \
        [--start 1] [--count 0] [--gap 300] [--dry-run]

The manifest lists items in posting order:
    {"items": [{"type": "reel", "id": "r02", "video_url": "https://….mp4", "caption": "…"},
               {"type": "carousel", "slug": "pujo-dates-2026"}]}
Reels need a public MP4 URL. Carousels are the ones the deploy renders to /kit/carousels/ (marketing/carousels.py);
their slides and caption come from the published carousels.json. --start N resumes at the Nth item (1-based) after a
failed run, so nothing is posted twice. Same token and account as marketing.publish_ig.

Daily sets (marketing/footage/factory.py) are read from the live site with --date: items carry "at" (HH:MM IST) and
the run waits for each slot; --window am|pm posts only the slots before / from 17:00, so each half fits in one job.
Video stories ({"type": "story", "video_url"}) are posted as Stories; photo posts ({"type": "photo", "image_urls"}) as
a single image or, with several, a carousel. A daily set posts only once its date is listed
in marketing/daily/approved.txt (the owner approves each day's set the evening before).
"""
import datetime as dt
import argparse
import json
import os
import sys
import time
import urllib.error

from pathlib import Path

from .kit import SITE
from .publish_ig import get_json, graph

KIT_CAROUSELS = SITE + "kit/carousels/"


def wait_ready(cid, token, tries=90, every=5):
    """Instagram fetches and processes media asynchronously; videos can take a few minutes."""
    for _ in range(tries):
        st = graph("GET", cid, token, fields="status_code").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise SystemExit(f"Instagram could not process container {cid} ({st})")
        time.sleep(every)
    raise SystemExit(f"container {cid} still not ready after {tries * every}s")


def carousel_caption(c):
    return f"{c['caption_en']}\n\n{c['caption_bn']}\n\n{c['hashtags']}"


def resolve(item, spec):
    """Turns a manifest item into what gets posted: kind, media URLs and caption."""
    if item["type"] == "photo":  # pure photography: one image, or a carousel of up to 10
        return {"label": item["id"], "kind": "photo", "urls": item["image_urls"], "caption": item.get("caption") or "",
                "at": item.get("at")}
    if item["type"] in ("reel", "story"):
        return {"label": item["id"], "kind": item["type"], "urls": [item["video_url"]], "caption": item.get("caption") or "",
                "at": item.get("at")}
    if item["type"] == "carousel":
        c = next((c for c in spec["carousels"] if c["slug"] == item["slug"]), None)
        if not c:
            raise SystemExit(f"carousel {item['slug']} is not in {KIT_CAROUSELS}carousels.json")
        urls = [f"{KIT_CAROUSELS}{c['id']}/slide-{i:02d}.jpg" for i in range(1, len(c["slides"]) + 1)]
        return {"label": c["id"], "kind": "carousel", "urls": urls, "caption": item.get("caption") or carousel_caption(c)}
    raise SystemExit(f"unknown item type {item['type']!r}")


def publish(p, user, token):
    if p["kind"] == "reel":
        cid = graph("POST", f"{user}/media", token, media_type="REELS", video_url=p["urls"][0],
                    caption=p["caption"], share_to_feed="true")["id"]
    elif p["kind"] == "story":
        cid = graph("POST", f"{user}/media", token, media_type="STORIES", video_url=p["urls"][0])["id"]
    elif p["kind"] == "photo" and len(p["urls"]) == 1:
        cid = graph("POST", f"{user}/media", token, image_url=p["urls"][0], caption=p["caption"])["id"]
    else:
        kids = [graph("POST", f"{user}/media", token, image_url=u, is_carousel_item="true")["id"] for u in p["urls"]]
        for k in kids:
            wait_ready(k, token, tries=30)
        cid = graph("POST", f"{user}/media", token, media_type="CAROUSEL", children=",".join(kids),
                    caption=p["caption"])["id"]
    wait_ready(cid, token)
    return graph("POST", f"{user}/media_publish", token, creation_id=cid)["id"]


def reachable(url):
    try:
        import urllib.request
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers={"User-Agent": "pujo-parikrama"}), timeout=30) as r:
            return r.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
APPROVED = Path(__file__).resolve().parents[1] / "marketing" / "daily" / "approved.txt"


def approved(date):
    return APPROVED.exists() and date in APPROVED.read_text(encoding="utf-8").split()


def wait_until(date, at, last, min_gap):
    """Sleep until the item's IST slot, and at least min_gap after the previous post (a late start never bunches)."""
    when = dt.datetime.fromisoformat(f"{date}T{at}:00").replace(tzinfo=IST).timestamp() if at else 0
    delay = max(when, last + min_gap if last else 0) - time.time()
    if delay > 0:
        print(f"waiting {delay / 60:.0f} min for {at or 'the gap'}", flush=True)
        time.sleep(delay)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("manifest", nargs="?", help="batch file (omit with --date)")
    ap.add_argument("--date", help="daily set: read SITE/kit/reels/<date>/manifest.json and post at each item's slot")
    ap.add_argument("--window", choices=["am", "pm", "all"], default="all", help="with --date: slots before / from 17:00")
    ap.add_argument("--start", type=int, default=1, help="1-based item to start from")
    ap.add_argument("--count", type=int, default=0, help="how many items (0 = to the end)")
    ap.add_argument("--gap", type=int, default=300, help="seconds between posts")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.date:
        items = get_json(f"{SITE}kit/reels/{a.date}/manifest.json?cb={int(time.time())}")["items"]
        items = [i for i in items if a.window == "all" or (i.get("at", "00:00") < "17:00") == (a.window == "am")]
        if not approved(a.date) and not a.dry_run:
            print(f"{a.date} is not in marketing/daily/approved.txt yet: dry run.")
            a.dry_run = True
    else:
        items = json.load(open(a.manifest, encoding="utf-8"))["items"]
    spec = get_json(f"{KIT_CAROUSELS}carousels.json?cb={int(time.time())}") if any(i["type"] == "carousel" for i in items) else {}
    end = len(items) if a.count <= 0 else min(len(items), a.start - 1 + a.count)
    todo = [(n, resolve(items[n - 1], spec)) for n in range(a.start, end + 1)]
    user, token = os.environ.get("IG_USER_ID"), os.environ.get("IG_ACCESS_TOKEN")
    dry = a.dry_run or not (user and token)
    if dry and not a.dry_run:
        print("IG_USER_ID / IG_ACCESS_TOKEN not set: dry run.")
    missing = [u for _, p in todo for u in p["urls"] if not reachable(u)]
    if missing:
        raise SystemExit("not reachable, fix before posting:\n" + "\n".join(missing))
    failed, last = [], 0
    for k, (n, p) in enumerate(todo):
        head = f"#{n} {p.get('at') or ''} {p['kind']} {p['label']} ({len(p['urls'])} file{'s' if len(p['urls']) > 1 else ''})"
        if dry:
            print(f"[dry run] {head}\n{p['caption'][:160]}…\n")
            continue
        if a.date:
            wait_until(a.date, p.get("at"), last, min(a.gap, 1200))
        elif k:
            time.sleep(a.gap)
        try:
            print(f"{head} → media {publish(p, user, token)}", flush=True)
            last = time.time()
        except SystemExit as e:
            print(f"{head} FAILED: {e}  (resume with --start {n})", flush=True)
            failed.append(n)
            break  # stop here so a --start resume never posts anything twice
    if failed:
        raise SystemExit(f"failed items: {failed}")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
