"""Pick the Home banner photo from the guide's Wikimedia Commons photos (runs in CI; needs Pillow).

  python scripts/hero_photo.py candidates           # small previews -> data/hero_candidates/ (+ index.json)
  python scripts/hero_photo.py hero <n>             # candidate n -> app/img/hero.jpg (1200 px) + app/img/hero.json (credit)
  python scripts/hero_photo.py set "<title>|<title>…"  # banner slideshow: each Commons photo (by title) -> app/img/hero-<i>.jpg + app/img/heroes.json
  python scripts/hero_photo.py tiles ["key=File:Title.jpg;…"]  # photo tiles (areas with no pandal photos, Explore switcher)
                                                             # -> app/img/tiles/<key>.jpg + tiles.json; picks by search unless a file is given
"""
import io, json, sys, urllib.request
from pathlib import Path
from PIL import Image

PANDALS = ["bagbazar", "kumartuli_sarbojanin", "sovabazar_rajbari", "md_ali_park", "college_square", "tala_prattoy",
           "ahiritola", "singhi_park", "jagat_mukherjee", "kashi_bose_lane", "simla_byayam", "hatibagan"]
UA = {"User-Agent": "PujoParikrama/1.0 (https://shubhgptgrowth.github.io/Durga-Puja-2026/; banner photo)"}
OUT = Path("data/hero_candidates")

def photos():
    g = json.loads(Path("app/data/guide.json").read_text())
    out = []
    for p in g["pandals"]:
        if p["id"] in PANDALS:
            out += [{**ph, "pandal": p["id"], "pandal_name": p["name"]} for ph in p.get("photos", [])]
    return out

def fetch(url):
    return Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read())).convert("RGB")

def candidates():
    OUT.mkdir(parents=True, exist_ok=True)
    idx = []
    for i, ph in enumerate(photos()):
        try:
            im = fetch(ph["src"]); im.thumbnail((360, 360)); im.save(OUT / f"{i:02d}.jpg", quality=70)
            idx.append({"n": i, **ph, "w": im.width, "h": im.height})
        except Exception as e:
            print("skip", i, ph["title"], e)
    (OUT / "index.json").write_text(json.dumps(idx, indent=1, ensure_ascii=False))
    print(len(idx), "candidates")

def hero(n):
    ph = next(x for x in json.loads((OUT / "index.json").read_text()) if x["n"] == n)
    big = ph["src"].replace("/960px-", "/1600px-")
    try: im = fetch(big)
    except Exception: im = fetch(ph["src"])
    im.thumbnail((1200, 1200))
    Path("app/img").mkdir(exist_ok=True)
    im.save("app/img/hero.jpg", quality=78, optimize=True, progressive=True)
    Path("app/img/hero.json").write_text(json.dumps({k: ph[k] for k in ("title", "author", "license", "page", "year", "pandal", "pandal_name")}, ensure_ascii=False, indent=1))
    print("hero", im.size, ph["title"])

def slideshow(titles):
    g = json.loads(Path("app/data/guide.json").read_text())
    by_title = {ph["title"]: {**ph, "pandal": p["id"], "pandal_name": p["name"]} for p in g["pandals"] for ph in p.get("photos", [])}
    Path("app/img").mkdir(exist_ok=True)
    out = []
    for i, title in enumerate(t.strip() for t in titles.split("|") if t.strip()):
        ph = by_title[title]
        try: im = fetch(ph["src"].replace("/960px-", "/1600px-"))
        except Exception: im = fetch(ph["src"])
        im.thumbnail((1100, 1100))
        name = f"hero-{i + 1}.jpg"
        im.save(f"app/img/{name}", quality=74, optimize=True, progressive=True)
        out.append({"src": f"img/{name}", "w": im.width, "h": im.height, **{k: ph[k] for k in ("title", "author", "license", "page", "year", "pandal", "pandal_name")}})
        print(name, im.size, title)
    Path("app/img/heroes.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

# Tile photos: what to search Commons for, per tile. The first landscape-ish photo whose title has all the
# `need` words wins. Override any of them with "key=File:Exact title.jpg" on the command line.
TILES = {
    "east": (["Salt Lake Durga Puja", "Salt Lake FD Block Durga Puja", "Bidhannagar Durga Puja pandal", "Durga Puja Salt Lake Kolkata"], ["puja"]),
    "howrah": (["Howrah Durga Puja", "Howrah Durga Puja pandal", "Durga Puja Howrah 2023", "Howrah Bridge Durga Puja"], ["howrah"]),
    "parking": (["Kolkata yellow taxi Ambassador", "Kolkata yellow taxi", "Kolkata traffic Durga Puja night"], ["taxi|traffic"]),
    "pandals": (["Kolkata Durga Puja pandal lights night", "Durga Puja pandal Kolkata lighting"], ["pandal|puja"]),
    "food": (["Kolkata street food kathi roll", "Kathi roll Kolkata", "Kolkata street food"], ["roll|food"]),
}
API = "https://commons.wikimedia.org/w/api.php"


def commons_search(q, n=20):
    import urllib.parse
    p = {"action": "query", "format": "json", "generator": "search", "gsrsearch": f"{q} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": n,
         "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 960}
    with urllib.request.urlopen(urllib.request.Request(f"{API}?{urllib.parse.urlencode(p)}", headers=UA), timeout=40) as r:
        pages = (json.load(r).get("query") or {}).get("pages", {})
    return sorted(pages.values(), key=lambda x: x.get("index", 99))


def tiles(overrides=""):
    import re
    chosen = dict(x.split("=", 1) for x in overrides.split(";") if "=" in x)
    out_dir = Path("app/img/tiles"); out_dir.mkdir(parents=True, exist_ok=True)
    credits = {}
    for key, (queries, need) in TILES.items():
        pick = None
        for q in ([f'"{chosen[key].replace("File:", "")}"'] if key in chosen else queries):
            for pg in commons_search(q):
                ii = (pg.get("imageinfo") or [{}])[0]
                title = pg["title"]
                if key in chosen and title != chosen[key]:
                    continue
                if not ii.get("thumburl") or ii.get("width", 0) < 800 or ii.get("width", 1) < ii.get("height", 0) * 0.9:
                    continue
                if key not in chosen and not all(re.search(w, title, re.I) for w in need):
                    continue
                pick = (pg, ii); break
            if pick: break
        if not pick:
            print("no photo for", key); continue
        pg, ii = pick
        md = ii.get("extmetadata", {}); val = lambda k: re.sub(r"<[^>]+>", "", (md.get(k) or {}).get("value", "")).strip()
        im = fetch(ii["thumburl"]); im.thumbnail((720, 720))
        im.save(out_dir / f"{key}.jpg", quality=72, optimize=True, progressive=True)
        credits[key] = {"src": f"img/tiles/{key}.jpg", "title": pg["title"].replace("File:", ""), "author": val("Artist")[:80] or "Unknown",
                        "license": val("LicenseShortName") or "see source", "page": ii.get("descriptionurl")}
        print(key, im.size, pg["title"])
    (out_dir / "tiles.json").write_text(json.dumps(credits, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "tiles": tiles(sys.argv[2] if len(sys.argv) > 2 else "")
    elif mode == "candidates": candidates()
    elif mode == "set": slideshow(sys.argv[2])
    else: hero(int(sys.argv[2]))
