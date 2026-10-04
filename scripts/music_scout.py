"""Find official, embeddable YouTube uploads of Durga Puja music, and re-check the ones the app plays.

  python scripts/music_scout.py scout   # search YouTube; print candidates from official label channels
  python scripts/music_scout.py check   # verify every id in app/data/music.json still exists and allows embedding

Runs in CI (the dev sandbox can't reach YouTube). Uses the public results page and oEmbed; no API key.
oEmbed answers 401 for videos whose owner disabled embedding, and 404 for removed or private ones."""
import json, re, sys, urllib.parse, urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Accept-Language": "en-IN,en;q=0.9"}
QUERIES = [
    "Mahishasuramardini Birendra Krishna Bhadra full",
    "Bajlo Tomar Alor Benu Supriti Ghosh",
    "Jago Durga Mahishasuramardini",
    "Ya Chandi Madhukaitabhadi Mahalaya",
    "Durga Puja dhak original audio",
    "dhaker bajna durga puja",
    "dhunuchi naach dhak",
    "Sandhi puja dhak",
    "agomoni gaan",
    "Ya Devi Sarvabhuteshu Durga stuti",
    "Durga Saptashati path",
    "Aigiri Nandini Mahishasura Mardini stotram",
    "Bijoya Dashami song bengali",
    "Durga Puja Bengali songs jukebox",
    "Dhaker Tale Komor Dole",
    "Dugga Elo",
    "Durga Chalisa",
    "Jai Ambe Gauri aarti",
]
OFFICIAL = re.compile(r"saregama|prasar bharati|akashvani|all india radio|t-series|tseries|zee music|svf|amara muzik|times music|sony music|shemaroo|tips|ultra bhakti|rajshri|bhakti|angel records|atlantis|asha audio|sagarika|venus|wings music|eskay|orion|times (?:music )?spiritual|gaana|jhankar", re.I)

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read().decode("utf-8", "replace")

def oembed(vid):
    try:
        d = json.loads(get("https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(f"https://www.youtube.com/watch?v={vid}")))
        return {"ok": True, "title": d.get("title"), "channel": d.get("author_name")}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code}
    except Exception as e:  # network
        return {"ok": False, "status": str(e)}

def search(q):
    html = get("https://www.youtube.com/results?hl=en&gl=IN&search_query=" + urllib.parse.quote(q))
    m = re.search(r"ytInitialData\s*=\s*({.*?});</script>", html, re.S)
    if not m:
        return []
    out = []
    def walk(o):
        if isinstance(o, dict):
            v = o.get("videoRenderer")
            if v and v.get("videoId"):
                title = "".join(r.get("text", "") for r in v.get("title", {}).get("runs", []))
                ch = "".join(r.get("text", "") for r in v.get("ownerText", {}).get("runs", []))
                dur = v.get("lengthText", {}).get("simpleText", "")
                views = v.get("viewCountText", {}).get("simpleText", "")
                out.append({"id": v["videoId"], "title": title, "channel": ch, "duration": dur, "views": views})
            for x in o.values():
                walk(x)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(json.loads(m.group(1)))
    return out

def scout():
    for q in QUERIES:
        try:
            res = search(q)
        except Exception as e:
            print(f"## {q}: search failed: {e}"); continue
        print(f"## {q}  ({len(res)} results)")
        for r in res[:15]:
            off = bool(OFFICIAL.search(r["channel"]))
            emb = oembed(r["id"]) if off else {"ok": None}
            flag = "OFFICIAL" if off else "-"
            print(f"  [{flag}{' embed=' + str(emb['ok']) if off else ''}] {r['id']} | {r['channel']} | {r['duration']} | {r['views']} | {r['title']}")

def check():
    data = json.loads(Path("app/data/music.json").read_text())
    bad = 0
    tracks = {t["yt"]: t for st in data["stations"] for t in st["tracks"] if t.get("yt")}.values()
    for tr in tracks:
        r = oembed(tr["yt"])
        print(("OK  " if r["ok"] else "BAD ") + tr["yt"], tr["title"], "|", r.get("channel") or r.get("status"))
        bad += not r["ok"]
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    {"scout": scout, "check": check}[sys.argv[1] if len(sys.argv) > 1 else "scout"]()
