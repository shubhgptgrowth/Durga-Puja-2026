"""Finds real, reusable Durga Puja video on Wikimedia Commons for the reels pipeline.

    python3 commons_scan.py catalog.json      # run where commons.wikimedia.org is reachable

Keeps only CC BY / CC BY-SA / CC0 / public-domain clips that are at least 720p and 6 s long, with the author and
licence needed for the on-screen credit. Writes {title: {url, w, h, dur, license, author, page, query}}.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "PujoParikramaBot/1.0 (https://github.com/shubhgptgrowth/Durga-Puja-2026; footage research)"}
QUERIES = ["Durga Puja", "Durga Pujo", "Durgapuja", "Durga puja Kolkata", "pandal", "Dhunuchi", "dhak", "Sindoor Khela",
           "Sindur khela", "Kumartuli", "Durga idol", "Durga immersion", "Bijoya Dashami", "Durga Puja aarti",
           "Durga Puja procession", "Durga Puja dance", "Bonedi bari", "Mahalaya", "Durga Visarjan", "Chokkhu daan",
           "Kolkata festival", "Navaratri Kolkata", "Durga Puja Bangladesh", "Sarbojanin"]
RELEVANT = re.compile(r"durga|pujo|puja|pandal|dhak|dhunuchi|dhunachi|sindoor|sindur|kumartuli|mahalaya|visarjan|bisarjan|"
                      r"bijoya|sarbojanin|tarpan|chokkhu|devi boron|immersion", re.I)  # "Kolkata" alone pulls in car rallies


def api(**p):
    p["format"] = "json"
    u = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(p)
    for k in range(4):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40))
        except Exception:
            time.sleep(4 * (k + 1))
    return {}


def text(m, key):
    return re.sub(r"\s+", " ", re.sub("<[^>]+>", "", m.get(key, {}).get("value", ""))).strip()


def main(out):
    seen = {}
    for q in QUERIES:
        off = 0
        while off < 500:
            r = api(action="query", generator="search", gsrsearch=f"{q} filetype:video", gsrnamespace=6, gsrlimit=50,
                    gsroffset=off, prop="imageinfo", iiprop="url|size|extmetadata", iiurlwidth=320)
            for p in ((r.get("query") or {}).get("pages") or {}).values():
                ii = (p.get("imageinfo") or [{}])[0]
                m = ii.get("extmetadata", {})
                seen.setdefault(p["title"], dict(url=ii.get("url"), w=ii.get("width", 0), h=ii.get("height", 0),
                                                 dur=round(ii.get("duration") or 0, 1), license=text(m, "LicenseShortName"),
                                                 author=text(m, "Artist")[:80], page=ii.get("descriptionurl"), thumb=ii.get("thumburl"), query=q))
            if "continue" not in r:
                break
            off = r["continue"].get("gsroffset", off + 50)
        print(f"{q}: {len(seen)} so far", file=sys.stderr, flush=True)
    keep = {t: v for t, v in seen.items()
            if re.search(r"CC BY|CC0|Public domain", v["license"], re.I) and max(v["w"], v["h"]) >= 1280
            and v["dur"] >= 6 and RELEVANT.search(t)}
    json.dump(keep, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    mins = sum(v["dur"] for v in keep.values()) / 60
    print(f"found {len(seen)} videos; usable {len(keep)} ({mins:.0f} min), vertical "
          f"{sum(v['h'] > v['w'] for v in keep.values())}, 4K {sum(max(v['w'], v['h']) >= 3840 for v in keep.values())}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "catalog.json")
