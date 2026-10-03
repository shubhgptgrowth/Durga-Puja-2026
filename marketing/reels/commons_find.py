"""List CC-licensed Durga Puja / Kolkata footage and Bengali-instrument audio on Wikimedia Commons.

    python3 commons_find.py > footage.json

Prints [{id, title, url, w, h, dur, license, artist, page}]. Run where commons.wikimedia.org is reachable.
"""
import json, time, urllib.parse, urllib.request, re

UA = {"User-Agent": "PujoParikramaBot/1.0 (https://github.com/shubhgptgrowth/Durga-Puja-2026; reels research)"}
TITLES = [
    "A video clips of Durga puja celebration on tenth day where married ladies doing Sindur Khela.webm",
    "A video of Devi Boron ritual during Durga puja 2025 in Kolkata.webm",
    "Dhunuchi dance at Samajsevi Sangh V 20181017 112000.webm",
    "DurgaPuja2018 - Pandal of Ahiritola Sarbojonin in Kolkata 01.webm",
    "Durga Puja in Kolkata 2017 Video Time Lapse 01.webm",
    "Evening Aarti of Durga Puja during new normal days DSCN7208.webm",
    "Illuminated lamps during Sandhi Puja at Ballygaunge Cultural V 20181017 123811.webm",
    "Maha Ashtami Puspanjali at Kolkata 2021.webm",
    "Maha Ashtami Sandhi puja at Ballygaunge Cultural V 20181017 124615.webm",
    "Video clip of Durga puja 2023 in Kolkata 01.webm",
    "Video clip of Durga puja 2023 in Kolkata 02.webm",
    "Video clip of Durga puja 2023 in Kolkata 03.webm",
    "Video of Drone doing coverage during Mahastami Aarti of Durga Puja 2021 at Kolkata.webm",
    "Bijaya Dashami.webm",
    "Sindoor Khela 01.webm", "Sindoor Khela 02.webm", "Sindoor Khela 03.webm",
    "The Kumartuli Montage.webm",
    "Howrah Bridge Night View (Silent Video) Full HD 1080p HIGH FR60.webm",
    "Dakshineswar bound Kolkata Metro train arriving Mahatma Gandhi Road station.webm",
    "Puja dhak.ogg", "Raga Durga.ogg", "Raga Bhairava.ogg", "Raga Bahar.ogg",
]
SEARCH = ["Durga Puja Pandal Visiting Kolkata", "Durga Puja Spectators Kolkata", "Durga Idol Immersion Baja Kadamtala Ghat",
          "Sovabazar Royal Durga Idol Immersion", "Dancing Devotees Durga Idol Immersion", "Rhythm of Dhak membranophone",
          "Mallick Ghat Flower Market", "Durga idol baran Dashami", "Dhenki durga puja ambience", "Bagbazar Sarbojanin Durgotsav 2018"]


def api(**p):
    time.sleep(1.2)
    p["format"] = "json"
    u = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(p)
    for k in range(4):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))
        except Exception:
            time.sleep(8 * (k + 1))
    raise SystemExit("commons api failed")


titles = ["File:" + t for t in TITLES]
for q in SEARCH:
    for x in api(action="query", list="search", srsearch=q, srnamespace=6, srlimit=15)["query"]["search"]:
        if re.search(r"\.(webm|ogv|ogg|oga|mp3|flac)$", x["title"], re.I) and x["title"] not in titles:
            titles.append(x["title"])
out = []
for i in range(0, len(titles), 40):
    r = api(action="query", titles="|".join(titles[i:i + 40]), prop="imageinfo", iiprop="url|size|extmetadata")
    for p in r["query"]["pages"].values():
        ii = (p.get("imageinfo") or [{}])[0]
        m = ii.get("extmetadata", {})
        if not ii.get("url"):
            continue
        artist = re.sub("<[^>]+>", "", urllib.parse.unquote(m.get("Artist", {}).get("value", ""))).strip()
        out.append({"title": p["title"][5:], "url": ii["url"], "page": ii.get("descriptionurl"), "w": ii.get("width"), "h": ii.get("height"),
                    "dur": round(ii.get("duration") or 0, 1), "license": m.get("LicenseShortName", {}).get("value"), "artist": artist[:80]})
out.sort(key=lambda o: o["title"])
for i, o in enumerate(out):
    o["id"] = f"f{i:02d}"
print(json.dumps(out, ensure_ascii=False, indent=0))
