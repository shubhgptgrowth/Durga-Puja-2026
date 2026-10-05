"""Catalogue of real, reusable footage for the daily reels: Wikimedia Commons, Pexels and Pixabay.

    python -m marketing.footage.catalog OUT_DIR         # writes OUT_DIR/catalog.json and OUT_DIR/sheet-NN.jpg

Pexels and Pixabay need PEXELS_API_KEY / PIXABAY_API_KEY (free keys, stored as repository secrets); without them only
Commons is scanned. Every entry carries what the on-screen credit needs:
    id -> {source, url, w, h, dur, license, artist, label, page, thumb, query}
Ids are stable: cm-<hash> (Commons), px-<id> (Pexels), pb-<id> (Pixabay). The contact sheets label each thumbnail
with its id, so a reel can be planned by looking at them.
"""
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

from . import commons_scan

UA = {"User-Agent": "PujoParikramaBot/1.0 (https://github.com/shubhgptgrowth/Durga-Puja-2026; footage research)"}
STOCK_QUERIES = ["durga puja", "durga", "durga idol", "kolkata", "kolkata night", "dhunuchi", "dhak drum", "pandal",
                 "sindoor", "bengali festival", "bengali woman saree", "kumartuli", "goddess durga", "aarti",
                 "hindu festival india night", "marigold garland", "diya lamps", "idol immersion", "conch shell",
                 "howrah bridge", "kolkata tram", "kolkata street", "bengali sweets"]


def get(url, headers=None, tries=3):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={**UA, **(headers or {})}), timeout=40) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise
            time.sleep(3 * (k + 1))
        except Exception:
            time.sleep(3 * (k + 1))
    raise SystemExit(f"could not fetch {url}")


def pick_file(files, w_key="width", h_key="height"):
    """Smallest file whose long side is >= 1920 (sharp on a phone, light to download), else the largest."""
    files = [f for f in files if f.get(w_key) and f.get(h_key)]
    big = sorted((f for f in files if max(f[w_key], f[h_key]) >= 1920), key=lambda f: f[w_key] * f[h_key])
    return big[0] if big else max(files, key=lambda f: f[w_key] * f[h_key], default=None)


def pexels(key):
    out = {}
    for q in STOCK_QUERIES:
        for page in (1, 2):
            u = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode({"query": q, "per_page": 80, "page": page})
            try:
                r = json.loads(get(u, {"Authorization": key}))
            except urllib.error.HTTPError as e:
                raise SystemExit(f"Pexels API refused the key ({e.code}); check the PEXELS_API_KEY secret")
            for v in r.get("videos", []):
                f = pick_file([x for x in v.get("video_files", []) if x.get("file_type") == "video/mp4"])
                if not f or v.get("duration", 0) < 4:
                    continue
                out.setdefault(f"px-{v['id']}", dict(source="Pexels", url=f["link"], w=f["width"], h=f["height"],
                                                     dur=v["duration"], license="Pexels License",
                                                     artist=(v.get("user") or {}).get("name", ""),
                                                     label=re.sub(r"[-/]+", " ", v.get("url", "").rstrip("/").split("/")[-1]).strip()[:80],
                                                     page=v.get("url"), thumb=v.get("image"), query=q))
            if not r.get("next_page"):
                break
            time.sleep(0.4)
        print(f"pexels {q}: {len(out)}", file=sys.stderr, flush=True)
    return out


def pixabay(key):
    out = {}
    for q in STOCK_QUERIES:
        u = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode({"key": key, "q": q, "per_page": 200, "safesearch": "true"})
        try:
            r = json.loads(get(u))
        except urllib.error.HTTPError as e:
            raise SystemExit(f"Pixabay API refused the key ({e.code}); check the PIXABAY_API_KEY secret")
        for v in r.get("hits", []):
            vids = [dict(x, name=n) for n, x in (v.get("videos") or {}).items() if x.get("url")]
            f = pick_file(vids)
            if not f or v.get("duration", 0) < 4:
                continue
            out.setdefault(f"pb-{v['id']}", dict(source="Pixabay", url=f["url"], w=f["width"], h=f["height"],
                                                 dur=v["duration"], license="Pixabay Content License",
                                                 artist=v.get("user", ""), label=v.get("tags", "")[:80],
                                                 page=v.get("pageURL"), thumb=f.get("thumbnail"), query=q))
        print(f"pixabay {q}: {len(out)}", file=sys.stderr, flush=True)
        time.sleep(0.7)
    return out


def commons():
    tmp = "/tmp/commons_scan.json"
    commons_scan.main(tmp)
    out = {}
    for title, v in json.load(open(tmp, encoding="utf-8")).items():
        cid = "cm-" + hashlib.sha1(title.encode()).hexdigest()[:6]
        out[cid] = dict(source="Wikimedia Commons", url=v["url"], w=v["w"], h=v["h"], dur=v["dur"], license=v["license"],
                        artist=v["author"], label=title[5:].rsplit(".", 1)[0][:80], page=v["page"], thumb=v.get("thumb"),
                        query=v["query"])
    return out


def sheets(cat, out_dir, per=24):
    """Contact sheets: 6x4 thumbnails labelled with id, source, resolution and length."""
    from PIL import Image, ImageDraw, ImageFont
    ids = sorted(cat, key=lambda k: (cat[k]["source"], k))
    try:
        f = ImageFont.truetype("fonts/Poppins-SemiBold.ttf", 15)
    except OSError:
        f = ImageFont.load_default()
    n = 0
    for s in range(0, len(ids), per):
        sheet = Image.new("RGB", (6 * 220, 4 * 250), (20, 12, 12))
        d = ImageDraw.Draw(sheet)
        for k, cid in enumerate(ids[s:s + per]):
            x, y = (k % 6) * 220, (k // 6) * 250
            v = cat[cid]
            try:
                im = Image.open(io.BytesIO(get(v["thumb"]))).convert("RGB") if v.get("thumb") else None
            except SystemExit:
                im = None
            if im:
                im.thumbnail((210, 200))
                sheet.paste(im, (x + 5 + (210 - im.width) // 2, y + 5 + (200 - im.height) // 2))
            d.text((x + 6, y + 207), cid, font=f, fill=(255, 220, 140))
            d.text((x + 6, y + 227), f"{v['w']}x{v['h']} {v['dur']:.0f}s {v['source'][:9]}", font=f, fill=(230, 230, 230))
        n += 1
        sheet.save(os.path.join(out_dir, f"sheet-{n:02d}.jpg"), quality=82)
    return n


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    cat = commons()
    for env, fn in (("PEXELS_API_KEY", pexels), ("PIXABAY_API_KEY", pixabay)):
        if os.environ.get(env):
            cat.update(fn(os.environ[env]))
        else:
            print(f"{env} not set: skipping {fn.__name__}", file=sys.stderr)
    json.dump(cat, open(os.path.join(out_dir, "catalog.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    n = sheets(cat, out_dir)
    by = {}
    for v in cat.values():
        by[v["source"]] = by.get(v["source"], 0) + 1
    print(f"catalog: {len(cat)} clips {by}; {n} contact sheets")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "catalog")
