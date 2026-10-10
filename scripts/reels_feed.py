"""Build the app's Pujo Reels feed (app/data/reels.json) at deploy.

    IG_USER_ID=… IG_ACCESS_TOKEN=… python scripts/reels_feed.py --out app

Sources, newest first:
  1. Videos on @pujoparikrama.guide's own Instagram grid (our reels and the creator clips we repost with permission),
     read through the official Graph API with the same token marketing/publish_ig.py posts with. No scraping.
  2. data/raw/reels_2026.toml: links the owner adds by hand (Instagram reposts that aren't on the grid, Facebook or
     YouTube videos).
The app only embeds them (the video stays on Instagram/Facebook/YouTube, credited and linked back). Thumbnails of our
own posts are saved small into app/img/reels/ (not committed). Without the secrets only the hand-added links are used.
Stdlib only; Pillow is used for thumbnails when it is installed.
"""
import argparse
import datetime as dt
import io
import json
import os
import re
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTRA = ROOT / "data/raw/reels_2026.toml"
GUIDE = ROOT / "app/data/guide.json"
MAX_REELS = 60
OUR_HANDLE = "@pujoparikrama.guide"

# The only links the app will embed (app/reels.js accepts the same ones).
IG = re.compile(r"^https://(?:www\.)?instagram\.com/(?:[A-Za-z0-9_.]+/)?(reels?|p|tv)/([A-Za-z0-9_-]{5,})")
FB = re.compile(r"^https://(?:(?:www|m|web)\.facebook\.com/\S+|fb\.watch/[A-Za-z0-9_-]+/?)$")
YT = re.compile(r"^https://(?:(?:www|m)\.youtube\.com/(?:shorts/|watch\?v=)|youtu\.be/)([A-Za-z0-9_-]{11})")
SPONSORED = re.compile(r"#ad\b|#sponsored\b|paid partnership|#collabwith", re.I)
# Words that don't tell pandals apart ("Kumartuli Sarbojanin" and "Kumartuli Park Sarbojanin" both end in it).
GENERIC = {"sarbojanin", "sarbajanin", "sarvajanin", "durgotsav", "durgotsab", "durga", "puja", "pujo", "samity",
           "samiti", "club", "committee", "the", "sangha", "sangho"}


def source_of(url):
    """('ig'|'fb'|'yt', canonical url) for a link the app can embed, else None."""
    url = (url or "").strip()
    if m := IG.match(url):
        kind = "p" if m.group(1) == "p" else "reel"
        return "ig", f"https://www.instagram.com/{kind}/{m.group(2)}/"
    if m := YT.match(url):
        return "yt", f"https://www.youtube.com/shorts/{m.group(1)}"
    if FB.match(url):
        return "fb", url
    return None


def norm(s):
    return " " + re.sub(r"[^0-9a-zঀ-৿]+", " ", (s or "").lower()).strip() + " "


def pandal_matchers(guide):
    """(phrase, pandal id) pairs, longest first: each pandal's full name and Bengali name, plus its name without
    generic words and its id (as in a hashtag) when those don't also fit another pandal ("Behala" alone could be any of
    Behala's pandals, so it ties a reel to none)."""
    pandals = guide.get("pandals", [])
    full = {p["id"]: norm(p["name"]) for p in pandals}
    pairs = []
    for p in pandals:
        words = full[p["id"]].split()
        core = " ".join(w for w in words if w not in GENERIC)
        sure = {" ".join(words), norm(p.get("name_bn")).strip()}
        maybe = {core, p["id"].replace("_", " "), p["id"].replace("_", "")}
        for phrase in sure | {m for m in maybe if not any(f" {m} " in f for i, f in full.items() if i != p["id"])}:
            if len(phrase) >= 5:
                pairs.append((f" {phrase} ", p["id"]))
    return sorted(pairs, key=lambda x: -len(x[0]))


def match_pandal(text, matchers):
    t = norm(text)
    for phrase, pid in matchers:
        if phrase in t:
            return pid
    return None


def title_of(caption):
    """The caption's first line, without hashtags, at most 90 characters."""
    line = next((x.strip() for x in (caption or "").splitlines() if x.strip()), "")
    line = re.sub(r"(?:\s*#\w+)+\s*$", "", line).strip()
    return line if len(line) <= 90 else line[:89].rsplit(" ", 1)[0] + "…"


def credit_of(caption):
    """The creator a reposted clip is credited to ("@handle, used with permission"), else us."""
    m = re.search(r"(@[A-Za-z0-9_.]{2,30})[^@\n]{0,20}used with permission", caption or "", re.I)
    return m.group(1).rstrip(".") if m else OUR_HANDLE


def get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "pujo-parikrama"}), timeout=60) as r:
        return json.load(r)


def instagram_media(user, token, limit=100):
    """Our own posts, newest first, from the Graph API (Instagram Login or Facebook Login token)."""
    base = "https://graph.instagram.com/v21.0" if token.startswith("IG") else "https://graph.facebook.com/v21.0"
    fields = "id,caption,media_type,media_product_type,permalink,thumbnail_url,timestamp"
    url = f"{base}/{user}/media?" + urllib.parse.urlencode({"fields": fields, "limit": 50, "access_token": token})
    out = []
    while url and len(out) < limit:
        page = get_json(url)
        out += page.get("data", [])
        url = page.get("paging", {}).get("next")
    return out


def save_thumb(src, path):
    """Download a thumbnail and keep it small (360 px wide WebP when Pillow is there). Returns True on success."""
    try:
        with urllib.request.urlopen(urllib.request.Request(src, headers={"User-Agent": "pujo-parikrama"}), timeout=30) as r:
            data = r.read()
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data)).convert("RGB")
        im.thumbnail((360, 640))
        im.save(path, "WEBP", quality=70)
    except ImportError:
        path.write_bytes(data)
    except OSError:
        return False
    return True


def from_instagram(items, matchers, out_dir):
    reels = []
    for m in items:
        if m.get("media_type") != "VIDEO":
            continue
        src = source_of(m.get("permalink"))
        if not src:
            continue
        cap = m.get("caption") or ""
        reel = {"id": "ig" + m["id"], "src": src[0], "url": src[1], "title": title_of(cap), "credit": credit_of(cap),
                "pandal": match_pandal(cap, matchers), "at": (m.get("timestamp") or "")[:10], "thumb": ""}
        if SPONSORED.search(cap):
            reel["sponsored"] = True
        if m.get("thumbnail_url") and out_dir:
            rel = f"img/reels/{reel['id']}.webp"
            if save_thumb(m["thumbnail_url"], Path(out_dir) / rel):
                reel["thumb"] = rel
        reels.append(reel)
    return reels


def from_extra(entries, matchers, pandal_ids):
    reels = []
    for i, e in enumerate(entries):
        src = source_of(e.get("url"))
        if not src:
            print(f"::warning::reels_2026.toml: skipped {e.get('url')!r}, not an Instagram, Facebook or YouTube link")
            continue
        pandal = e.get("pandal") or match_pandal(e.get("title", ""), matchers)
        reel = {"id": f"x{i}", "src": src[0], "url": src[1], "title": (e.get("title") or "").strip()[:90],
                "credit": (e.get("credit") or "").strip(), "pandal": pandal if pandal in pandal_ids else None,
                "at": str(e.get("added") or ""), "thumb": ""}
        if e.get("sponsored"):
            reel["sponsored"] = True
        reels.append(reel)
    return reels


def build(ig_items, extra_entries, guide, out_dir=None, now=None):
    matchers = pandal_matchers(guide)
    pandal_ids = {p["id"] for p in guide.get("pandals", [])}
    reels = from_instagram(ig_items, matchers, out_dir) + from_extra(extra_entries, matchers, pandal_ids)
    seen, unique = set(), []
    for r in sorted(reels, key=lambda r: r["at"], reverse=True):   # newest first; a link is listed once
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)
    return {"updated": (now or dt.datetime.now(dt.timezone.utc)).isoformat(timespec="minutes"), "reels": unique[:MAX_REELS]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="app", help="site folder: writes data/reels.json and img/reels/ there")
    args = ap.parse_args(argv)
    guide = json.loads(GUIDE.read_text(encoding="utf-8"))
    extra = tomllib.loads(EXTRA.read_text(encoding="utf-8")).get("reel", []) if EXTRA.exists() else []
    user, token = os.environ.get("IG_USER_ID"), os.environ.get("IG_ACCESS_TOKEN")
    items = []
    if user and token:
        try:
            items = instagram_media(user, token)
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            print(f"::warning::Instagram media not read ({e}); the feed uses the hand-added links only")
    else:
        print("No IG_USER_ID / IG_ACCESS_TOKEN: the feed uses the hand-added links only")
    feed = build(items, extra, guide, out_dir=args.out)
    path = Path(args.out) / "data/reels.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(feed, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"reels: {len(feed['reels'])} ({sum(r['src'] == 'ig' for r in feed['reels'])} Instagram, "
          f"{sum(bool(r['pandal']) for r in feed['reels'])} tied to a pandal) -> {path}")


if __name__ == "__main__":
    sys.exit(main())
