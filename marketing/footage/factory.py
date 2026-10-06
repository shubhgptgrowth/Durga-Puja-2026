"""Daily reels factory: turns marketing/daily/<date>.json into the day's reels and video stories, a review page and
the posting manifest that marketing-batch reads.

    python -m marketing.footage.factory 2026-10-06 --catalog catalog/catalog.json --out out/2026-10-06

The plan lists the day's items in posting order:
    {"date": "2026-10-06", "items": [
      {"id": "r1", "type": "reel", "at": "12:30", "hook": "…", "bn": {"hook": "…", "segs": [...], "end": "…"},
       "segments": [[clip_id, start_s, secs, "English line", cx?], ...], "end": ["…", "…"], "music": ["au-dhak", 0],
       "caption": {"en": "…", "bn": "…", "tags": "…"}},
      {"id": "s1", "type": "story", "at": "10:30", "bn": {"segs": [...]}, "segments": [...]},
      {"id": "b01", "type": "reel", "at": "21:00", "video_url": "https://…", "caption": "…"}]}   # already rendered
Clip ids come from the footage catalogue (cm-/px-/pb-), from marketing/reels/footage.json (f00…), or are the app's
own audio (au-dhak, au-shankh, au-dhakhit). Output goes to the live site at /kit/reels/<date>/ (deploy pulls it in).
"""
import argparse
import hashlib
import html
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from ..kit import SITE

ROOT = Path(__file__).resolve().parents[2]
UA = {"User-Agent": "PujoParikramaBot/1.0 (https://github.com/shubhgptgrowth/Durga-Puja-2026)"}
AUDIO = {"au-dhak": "dhak", "au-dhakhit": "dhak_hit", "au-shankh": "shankh"}


def footage_index(catalog_path):
    """Every clip a plan may use: the scanned catalogue, the hand-picked footage.json, and the app's audio."""
    idx = {}
    legacy = json.load(open(ROOT / "marketing/reels/footage.json", encoding="utf-8"))
    for k, v in legacy.items():
        idx[k] = dict(v, source=v.get("source", "Wikimedia Commons"))
    if catalog_path and os.path.exists(catalog_path):
        idx.update(json.load(open(catalog_path, encoding="utf-8")))
    cr = json.load(open(ROOT / "marketing/creators/clips.json", encoding="utf-8"))["clips"]
    for k, v in cr.items():  # other creators' clips, usable only with their recorded permission (check() enforces it)
        if k != "cr-example":
            idx[k] = dict(source="Instagram" if "instagram.com" in v.get("page", "") else "Creator", url=v["url"],
                          w=v.get("w", 1080), h=v.get("h", 1920), dur=v.get("dur", 0), label=v.get("label", ""),
                          artist=v["handle"], license="used with permission", page=v.get("page"),
                          permission=v.get("permission", ""), collab=v.get("collab", False))
    credits = json.load(open(ROOT / "app/audio/credits.json", encoding="utf-8"))
    for k, name in AUDIO.items():
        c = credits[name]
        idx[k] = dict(source="Wikimedia Commons", local=str(ROOT / f"app/audio/{name}.mp3"), license=c["license"],
                      artist=c["author"], label=c["title"].replace("File:", "").rsplit(".", 1)[0][:60], page=c["page"])
    return idx


def download(url, dest):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r, open(str(dest) + ".part", "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    os.replace(str(dest) + ".part", dest)


def fetch(cid, e, src_dir):
    """Source file for a clip id, downloaded once into src_dir (cached between runs)."""
    have = [p for p in Path(src_dir).glob(f"{cid}.*") if not p.name.endswith(".part")]
    if have:
        return have[0]
    if e.get("local"):
        dest = Path(src_dir) / f"{cid}{Path(e['local']).suffix}"
        shutil.copy(e["local"], dest)
        return dest
    url = e["url"]
    name = url.rsplit("/", 1)[-1].split("?")[0]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else "mp4"
    video = max(e.get("w", 0), e.get("h", 0)) > 0
    if e["source"] == "Wikimedia Commons" and video and (ext in ("ogv", "ogg") or max(e["w"], e["h"]) > 1920):
        # Commons keeps 1080p transcodes next to big or old-format originals: lighter and always decodable
        base = url.split("/commons/", 1)
        for s in ("1080p.vp9.webm", "1080p.webm"):
            dest = Path(src_dir) / f"{cid}.webm"
            try:
                download(f"{base[0]}/commons/transcoded/{base[1]}/{name}.{s}", dest)
                return dest
            except Exception:
                pass
    dest = Path(src_dir) / f"{cid}.{ext if ext in ('mp4', 'webm', 'ogv', 'ogg', 'mov', 'mp3', 'jpg', 'png') else 'mp4'}"
    download(url, dest)
    return dest


def voice_file(url, src_dir):
    dest = Path(src_dir) / ("vo-" + hashlib.sha1(url.encode()).hexdigest()[:12] + Path(url.split("?")[0]).suffix)
    if not dest.exists():
        download(url, dest)
    return str(dest)


def check(plan, idx):
    """Every clip exists and every cut fits inside its clip, before anything is downloaded."""
    errs = []
    for it in plan["items"]:
        if it.get("video_url"):
            continue
        for s in it["segments"]:
            e = idx.get(s[0])
            if not e:
                errs.append(f"{it['id']}: unknown clip {s[0]}")
            elif e.get("license") == "used with permission" and not (e.get("permission") and e.get("url")):
                errs.append(f"{it['id']}: {s[0]} ({e['artist']}) has no recorded permission or file yet")
            elif e.get("dur") and s[1] + s[2] > e["dur"] + 0.05:
                errs.append(f"{it['id']}: {s[0]} is {e['dur']}s, cut ends at {s[1] + s[2]}s")
        vo = it.get("vo")
        if vo and not (len(vo.get("lines", [])) == len(vo.get("urls", [])) == len(it["segments"])):
            errs.append(f"{it['id']}: voiceover needs one line and one audio url per shot")
        segs = (it.get("bn") or {}).get("segs", [])
        if it.get("bn") and not vo and len(segs) != len(it["segments"]):
            errs.append(f"{it['id']}: {len(it['segments'])} shots but {len(segs)} Bengali lines")
    if errs:
        raise SystemExit("plan problems:\n" + "\n".join(errs))


def qa_strip(mp4, jpg):
    d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)]))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vf", f"fps=8/{d},scale=180:320,tile=8x1",
                    "-frames:v", "1", str(jpg)], check=True)
    return d


def review_page(date, items, out):
    rows = []
    for it in items:
        cap = html.escape(it.get("caption") or "(story: no caption)")
        rows.append(f"""<section><h2>{html.escape(it['at'])} · {it['type']} · {html.escape(it['id'])}</h2>
<video src="{html.escape(it['video_url'])}" controls playsinline preload="metadata"></video>
<pre>{cap}</pre></section>""")
    (out / "index.html").write_text(f"""<!doctype html><html lang="bn"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Reels review {date}</title>
<style>body{{font-family:system-ui,sans-serif;background:#fbf3e4;color:#2b1410;margin:0;padding:16px;max-width:760px;margin:auto}}
h1{{color:#b21826}}section{{background:#fff;border:3px solid #b21826;border-radius:14px;padding:12px;margin:16px 0}}
video{{width:100%;max-height:70vh;background:#000;border-radius:8px}}pre{{white-space:pre-wrap;font:14px/1.45 system-ui}}</style>
<h1>পুজো পরিক্রমা · {date}</h1><p>{len(items)} items in posting order (IST). Nothing posts until this day is approved.</p>
{''.join(rows)}</html>""", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("date")
    ap.add_argument("--catalog", default="catalog/catalog.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--src", default="src")
    ap.add_argument("--base-url", help="where the videos will be served (default: the live /kit/reels/<date>/)")
    a = ap.parse_args(argv)
    from ..reels import build2  # needs Pillow and fonts/, so only when rendering
    plan = json.load(open(ROOT / f"marketing/daily/{a.date}.json", encoding="utf-8"))
    idx = footage_index(a.catalog)
    check(plan, idx)
    out, tmp = Path(a.out), Path(a.out) / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    os.makedirs(a.src, exist_ok=True)
    base = a.base_url or f"{SITE}kit/reels/{a.date}/"
    pfx = a.date[5:7] + a.date[8:10]
    items = []
    for it in sorted(plan["items"], key=lambda x: x["at"]):
        fid = f"{pfx}-{it['id']}"
        entry = {"type": it["type"], "id": fid, "at": it["at"]}
        if it.get("video_url"):
            entry.update(video_url=it["video_url"], caption=it.get("caption"))
        else:
            music = [it["music"]] if it.get("music") and not it.get("vo") else []
            for s in it["segments"] + music + ([it["end_clip"]] if it.get("end_clip") else []):
                fetch(s[0], idx[s[0]], a.src)
            reel = dict(it, id=fid)
            if it.get("vo"):  # voiceover lines, one per shot (generated ahead, see marketing/footage/voice.py)
                reel["vo_files"] = [voice_file(u, a.src) if u else None for u in it["vo"]["urls"]]
            if it["type"] == "story":
                reel.pop("end", None)
                reel.pop("caption", None)
            secs = build2.build(reel, idx, a.src, str(out), str(tmp))
            entry["video_url"] = base + f"{fid}.mp4"
            cap = out / f"{fid}.caption.txt"
            entry["caption"] = cap.read_text(encoding="utf-8").strip() if cap.exists() else None
            qa_strip(out / f"{fid}.mp4", out / f"qa_{fid}.jpg")
            print(f"built {fid} {it['type']} {secs:.1f}s", flush=True)
        items.append(entry)
    json.dump({"date": a.date, "items": items}, open(out / "manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    review_page(a.date, items, out)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"{len(items)} items → {out} (review: {base}index.html)")


if __name__ == "__main__":
    sys.exit(main())
