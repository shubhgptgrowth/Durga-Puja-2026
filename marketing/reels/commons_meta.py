"""Add Wikimedia Commons photos to the footage list, with licence, author and a 2400 px download URL.

    python3 commons_meta.py photos3.tsv footage.json > footage3.json

photos3.tsv: id<TAB>Commons file title<TAB>short label. Keeps only CC BY / CC BY-SA / CC0 / public-domain files.
Run where commons.wikimedia.org is reachable.
"""
import json, re, sys, time, urllib.parse, urllib.request

UA = {"User-Agent": "PujoParikramaBot/1.0 (https://github.com/shubhgptgrowth/Durga-Puja-2026; reels research)"}


def api(**p):
    p["format"] = "json"
    u = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(p)
    for k in range(4):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))
        except Exception:
            time.sleep(6 * (k + 1))
    raise SystemExit("commons api failed")


rows = [l.rstrip("\n").split("\t") for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
footage = json.load(open(sys.argv[2], encoding="utf-8"))
by_title = {"File:" + t: (i, label) for i, t, label in rows}
titles = list(by_title)
for k in range(0, len(titles), 40):
    r = api(action="query", titles="|".join(titles[k:k + 40]), prop="imageinfo", iiprop="url|size|extmetadata",
            iiurlwidth=2400)
    norm = {n["to"]: n["from"] for n in r["query"].get("normalized", [])}
    for p in r["query"]["pages"].values():
        ii = (p.get("imageinfo") or [{}])[0]
        m = ii.get("extmetadata", {})
        lic = m.get("LicenseShortName", {}).get("value", "")
        sid, label = by_title[norm.get(p["title"], p["title"])]
        if not ii.get("url") or not re.search(r"CC BY|CC0|Public domain", lic):
            print(f"skip {sid}: {lic or 'missing'}", file=sys.stderr)
            continue
        artist = re.sub(r"\s+", " ", re.sub("<[^>]+>", "", m.get("Artist", {}).get("value", ""))).strip()
        footage[sid] = {"url": ii.get("thumburl") or ii["url"], "page": ii["descriptionurl"], "w": ii["width"],
                        "h": ii["height"], "license": lic, "artist": artist, "label": label + " (photo)"}
    time.sleep(1)
json.dump(footage, sys.stdout, ensure_ascii=False, indent=1)
