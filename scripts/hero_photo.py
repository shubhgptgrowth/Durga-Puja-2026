"""Pick the Home banner photo from the guide's Wikimedia Commons photos (runs in CI; needs Pillow).

  python scripts/hero_photo.py candidates           # small previews -> data/hero_candidates/ (+ index.json)
  python scripts/hero_photo.py hero <n>             # candidate n -> app/img/hero.jpg (1200 px) + app/img/hero.json (credit)
  python scripts/hero_photo.py set "<title>|<title>…"  # banner slideshow: each Commons photo (by title) -> app/img/hero-<i>.jpg + app/img/heroes.json
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

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "candidates": candidates()
    elif mode == "set": slideshow(sys.argv[2])
    else: hero(int(sys.argv[2]))
