"""Freely licensed pujo sounds from Wikimedia Commons, self-hosted so they play without ads or branding.

  python scripts/audio_fetch.py scout                         # list Commons audio/video for dhak, conch, ulu, kansor
  python scripts/audio_fetch.py get "File:X.ogg|start|secs|out"  # cut + encode -> app/audio/<out>.mp3 (+ credits.json)

Runs in CI (needs ffmpeg; the dev sandbox can't reach Commons)."""
import json, re, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "PujoParikrama/1.0 (https://shubhgptgrowth.github.io/Durga-Puja-2026/; sounds)"}
QUERIES = ["dhak", "dhaki", "dhak drum", "Durga Puja drum", "dhak Durga Puja", "conch shell blowing", "shankha", "shankh", "conch sound",
           "ululation Bengali", "uludhwani", "ulu dhwani", "kansar ghanta", "kasor", "Durga Puja aarti", "Durga Puja dhunuchi", "sandhi puja"]

def api(**p):
    p.update(format="json")
    return json.loads(urllib.request.urlopen(urllib.request.Request(API + "?" + urllib.parse.urlencode(p), headers=UA), timeout=30).read())

def info(titles):
    d = api(action="query", titles="|".join(titles), prop="imageinfo", iiprop="url|size|mime|extmetadata|mediatype")
    out = []
    for pg in d["query"]["pages"].values():
        ii = (pg.get("imageinfo") or [{}])[0]
        md = ii.get("extmetadata", {})
        g = lambda k: re.sub("<[^>]+>", "", md.get(k, {}).get("value", ""))[:80]
        out.append({"title": pg["title"], "mime": ii.get("mime"), "url": ii.get("url"), "size": ii.get("size"), "duration": ii.get("duration"),
                    "license": g("LicenseShortName"), "author": g("Artist"), "page": ii.get("descriptionurl")})
    return out

def scout():
    seen = set()
    for q in QUERIES:
        d = api(action="query", list="search", srnamespace=6, srlimit=25, srsearch=f"{q} filetype:audio|video")
        titles = [x["title"] for x in d["query"]["search"] if x["title"] not in seen]
        seen.update(titles)
        print(f"## {q} ({len(titles)})")
        for i in range(0, len(titles), 40):
            for f in info(titles[i:i + 40]):
                print(f"  {f['title']} | {f['mime']} | {f['duration']}s | {f['license']} | {f['author']}")

def strongest_onset(src, rate=22050, win=441):
    """Time (s) of the biggest jump in short-window energy, i.e. the hardest drum stroke."""
    import array
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"],
                         check=True, capture_output=True).stdout
    pcm = array.array("h", raw)
    energy = [sum(x * x for x in pcm[i:i + win]) / win for i in range(0, len(pcm) - win, win)]
    best = max(range(1, len(energy)), key=lambda i: energy[i] - energy[i - 1])
    return best * win / rate

def get(specs):
    Path("app/audio").mkdir(parents=True, exist_ok=True)
    cred_p = Path("app/audio/credits.json")
    credits = json.loads(cred_p.read_text()) if cred_p.exists() else {}
    for spec in specs.split(";"):
        title, start, secs, out = [x.strip() for x in spec.split("|")]
        f = info([title])[0]
        src = Path("/tmp/src") ; src.write_bytes(urllib.request.urlopen(urllib.request.Request(f["url"], headers=UA), timeout=120).read())
        if start == "peak":  # a single stroke: the strongest onset in the recording
            start = f"{max(0.0, strongest_onset(src) - 0.02):.3f}"
            print("  strongest onset at", start)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", start, "-t", secs, "-i", str(src), "-vn", "-ac", "2", "-ar", "44100",
               "-af", "loudnorm=I=-16:TP=-1.5,afade=t=in:d=0.05,areverse,afade=t=in:d=0.4,areverse", "-b:a", "112k", f"app/audio/{out}.mp3"]
        subprocess.run(cmd, check=True)
        credits[out] = {k: f[k] for k in ("title", "author", "license", "page")}
        print("wrote", out, f["title"], f["license"], f["author"])
    cred_p.write_text(json.dumps(credits, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    scout() if sys.argv[1] == "scout" else get(sys.argv[2])
