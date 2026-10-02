"""Optional: post the day's kit cards to Instagram through the official Graph API (content publishing).

    IG_USER_ID=… IG_ACCESS_TOKEN=… python -m marketing.publish_ig [--date 2026-10-11] [--dry-run] [--only post|story]

Needs an Instagram professional account linked to a Facebook Page, and a long-lived token with
instagram_basic + instagram_content_publish (docs/MARKETING.md → "Instagram auto-posting").
Images are fetched by Instagram from the published kit (https://…/kit/<date>/<card>.jpg), so the
day's deploy must have run first. Without credentials, or with --dry-run, it only prints the plan.
Stdlib only.
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from .kit import SITE

GRAPH = "https://graph.facebook.com/v21.0"


def ist_today():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date()


def get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "pujo-parikrama"}), timeout=60) as r:
        return json.load(r)


def graph(method, path, token, **params):
    params["access_token"] = token
    data = urllib.parse.urlencode(params).encode()
    url = f"{GRAPH}/{path}"
    req = urllib.request.Request(url if method == "POST" else f"{url}?{data.decode()}", data=data if method == "POST" else None, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Graph API {path} failed: {e.code} {e.read().decode()[:400]}")


def caption(card):
    both = f"{card['caption_en']}\n\n{card['caption_bn']}"
    return both if len(both) <= 2200 else card["caption_en"]


def publish(card, user, token):
    image = SITE + "kit/" + card["file"]
    params = {"image_url": image}
    if card["format"] == "story":
        params["media_type"] = "STORIES"
    else:
        params["caption"] = caption(card)
    c = graph("POST", f"{user}/media", token, **params)
    for _ in range(30):  # wait until Instagram has fetched and processed the image
        st = graph("GET", c["id"], token, fields="status_code")
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise SystemExit(f"Instagram could not process {image}")
        time.sleep(4)
    return graph("POST", f"{user}/media_publish", token, creation_id=c["id"])["id"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", help="YYYY-MM-DD (default: today in IST)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", choices=["post", "story"])
    a = ap.parse_args(argv)
    day = a.date or ist_today().isoformat()
    user, token = os.environ.get("IG_USER_ID"), os.environ.get("IG_ACCESS_TOKEN")
    try:
        assets = get_json(f"{SITE}kit/{day}/assets.json?cb={int(time.time())}")
    except urllib.error.HTTPError as e:
        print(f"No kit for {day} ({e.code}); outside the campaign or not deployed yet.")
        return
    except urllib.error.URLError as e:
        raise SystemExit(f"Could not reach the published kit: {e.reason}")
    cards = [c for c in assets["cards"] if not a.only or c["format"] == a.only]
    dry = a.dry_run or not (user and token)
    if dry and not a.dry_run:
        print("IG_USER_ID / IG_ACCESS_TOKEN not set: dry run.")
    for c in cards:
        if dry:
            print(f"[dry run] would post {c['format']:5} {SITE}kit/{c['file']}\n{caption(c) if c['format'] == 'post' else '(story, no caption)'}\n")
            continue
        mid = publish(c, user, token)
        print(f"posted {c['format']} {c['id']} → media {mid}")
    if not cards:
        print(f"Nothing to post for {day}.")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
