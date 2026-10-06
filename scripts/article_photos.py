"""Photos for the knowledge articles, from Wikimedia Commons (runs in CI; needs Pillow). See content/knowledge/photos.toml.

  python scripts/article_photos.py candidates [key,key…]   numbered contact sheets → data/photo_candidates/<key>.jpg + <key>.json
  python scripts/article_photos.py pandals                 contact sheets of the guide's pandal photos → data/photo_candidates/pandals-<n>.jpg
  python scripts/article_photos.py fetch                   chosen files → app/img/guide/<key>.webp, <key>-600.webp + photos.json
"""
import io
import json
import re
import sys
import tomllib
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
TOML = ROOT / "content" / "knowledge" / "photos.toml"
CANDS = ROOT / "data" / "photo_candidates"
OUT = ROOT / "app" / "img" / "guide"
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "PujoParikrama/1.0 (https://pujoparikramaguide.in/; article photos; workdesk94@gmail.com)"}
FREE = re.compile(r"^(CC0( 1\.0)?|Public domain|PD(-\w+)*|CC BY(-SA)?( \d\.\d)?( [a-z]{2,3})?|Attribution|No restrictions)$", re.I)   # no NC / ND


def get_json(params):
    url = f"{API}?{urllib.parse.urlencode({'format': 'json', **params})}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
        return json.load(r)


def image(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return ImageOps.exif_transpose(Image.open(io.BytesIO(r.read()))).convert("RGB")


def text(md, k):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", (md.get(k) or {}).get("value", ""))).strip()


def info(pg):
    """A Commons page → {title, url, w, h, author, license, license_url, page}, or None if not freely licensed."""
    ii = (pg.get("imageinfo") or [{}])[0]
    md = ii.get("extmetadata", {})
    lic = text(md, "LicenseShortName")
    if not ii.get("thumburl") or text(md, "NonFree").lower() == "true" or not FREE.match(lic or "-"):
        return None
    return {"title": pg["title"], "url": ii["thumburl"], "w": ii.get("width", 0), "h": ii.get("height", 0),
            "author": text(md, "Artist")[:90] or "Unknown", "license": lic, "license_url": text(md, "LicenseUrl"),
            "page": ii.get("descriptionurl")}


def search(q, width, n=24):
    j = get_json({"action": "query", "generator": "search", "gsrsearch": f"{q} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": n,
                  "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": width})
    return sorted((j.get("query") or {}).get("pages", {}).values(), key=lambda x: x.get("index", 99))


def by_title(title, width):
    j = get_json({"action": "query", "titles": title, "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": width})
    return next(iter(j["query"]["pages"].values()))


def sheet(items, path, cols=4, tile=(300, 200)):
    """Numbered contact sheet of thumbnails."""
    rows = (len(items) + cols - 1) // cols
    W, H = tile
    out = Image.new("RGB", (cols * W, rows * (H + 22)), "white")
    d = ImageDraw.Draw(out)
    try:
        font = ImageFont.load_default(size=18)
    except TypeError:
        font = ImageFont.load_default()
    for i, (im, label) in enumerate(items):
        x, y = (i % cols) * W, (i // cols) * (H + 22)
        out.paste(ImageOps.fit(im, (W - 4, H - 4)), (x + 2, y + 2))
        d.rectangle((x + 2, y + 2, x + 34, y + 26), fill="black")
        d.text((x + 8, y + 4), str(i), fill="yellow", font=font)
        d.text((x + 4, y + H), label[:40], fill="black", font=font)
    out.save(path, quality=72)


def candidates(only=""):
    cfg = tomllib.loads(TOML.read_text(encoding="utf-8"))
    keys = [k for k in (only.split(",") if only else cfg) if k and not cfg[k].get("file")]
    CANDS.mkdir(parents=True, exist_ok=True)
    for key in keys:
        seen, found = set(), []
        for q in cfg[key].get("q", []):
            try:
                pages = search(q, 330)
            except Exception as e:
                print("search failed", key, q, e)
                continue
            for pg in pages:
                x = info(pg)
                if x and x["title"] not in seen and x["w"] >= 800 and not x["title"].lower().endswith((".tif", ".tiff")):
                    seen.add(x["title"])
                    found.append(x)
            if len(found) >= 12:
                break
        found = found[:12]
        items = []
        for x in found:
            try:
                items.append((image(x["url"]), x["title"].replace("File:", "")))
            except Exception as e:
                print("skip", x["title"], e)
                found = [f for f in found if f is not x]
        if not items:
            print("no candidates for", key)
            continue
        sheet(items, CANDS / f"{key}.jpg")
        (CANDS / f"{key}.json").write_text(json.dumps([{"n": i, "title": x["title"], "w": x["w"], "h": x["h"], "license": x["license"],
                                                         "author": x["author"]} for i, x in enumerate(found)], indent=1, ensure_ascii=False))
        print(key, len(items), "candidates")


def pandals():
    g = json.loads((ROOT / "app" / "data" / "guide.json").read_text(encoding="utf-8"))
    photos = [(p["name"], ph) for p in g["pandals"] for ph in p.get("photos", [])]
    CANDS.mkdir(parents=True, exist_ok=True)
    for s in range(0, len(photos), 20):
        chunk, items, idx = photos[s:s + 20], [], []
        for name, ph in chunk:
            try:
                items.append((image(ph["src"].replace("/960px-", "/330px-")), name))
                idx.append({"n": len(idx), "title": "File:" + ph["page"].rsplit("File:", 1)[-1].replace("_", " "), "pandal": name})
            except Exception as e:
                print("skip", ph["title"], e)
        n = s // 20 + 1
        sheet(items, CANDS / f"pandals-{n}.jpg", cols=5, tile=(240, 160))
        (CANDS / f"pandals-{n}.json").write_text(json.dumps(idx, indent=1, ensure_ascii=False))
        print("pandals", n, len(items))


def fetch():
    cfg = tomllib.loads(TOML.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    credits_file = OUT / "photos.json"
    credits = json.loads(credits_file.read_text(encoding="utf-8")) if credits_file.exists() else {}
    for key, c in cfg.items():
        file = c.get("file")
        if not file:
            continue
        file = file if file.startswith("File:") else "File:" + file
        if credits.get(key, {}).get("title") == file and (OUT / f"{key}.webp").exists():
            credits[key]["caption"] = c.get("caption", "")
            continue
        x = info(by_title(file, 1280))
        if not x:
            print("NOT FREE or missing, skipped:", key, file)
            continue
        im = image(x["url"])
        im.thumbnail((1200, 1200))
        im.save(OUT / f"{key}.webp", quality=72, method=6)
        small = im.copy()
        small.thumbnail((600, 600))
        small.save(OUT / f"{key}-600.webp", quality=70, method=6)
        credits[key] = {"title": file, "author": x["author"], "license": x["license"], "license_url": x["license_url"], "page": x["page"],
                        "w": im.width, "h": im.height, "caption": c.get("caption", "")}
        print(key, im.size, file)
    for key in list(credits):   # photos no longer chosen
        if key not in cfg or not cfg[key].get("file"):
            credits.pop(key)
            for f in (OUT / f"{key}.webp", OUT / f"{key}-600.webp"):
                f.unlink(missing_ok=True)
    credits_file.write_text(json.dumps(dict(sorted(credits.items())), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "candidates"
    arg = sys.argv[2] if len(sys.argv) > 2 else ""
    {"candidates": lambda: candidates(arg), "pandals": pandals, "fetch": fetch}[mode]()
