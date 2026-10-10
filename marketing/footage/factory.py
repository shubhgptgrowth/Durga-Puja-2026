"""Daily reels factory: turns marketing/daily/<date>.json into the day's reels and video stories, a review page and
the posting manifest that marketing-batch reads.

    python -m marketing.footage.factory 2026-10-06 --catalog catalog/catalog.json --out out/2026-10-06

The plan lists the day's items in posting order:
    {"date": "2026-10-06", "items": [
      {"id": "r1", "type": "reel", "at": "12:30", "hook": "…", "bn": {"hook": "…", "segs": [...], "end": "…"},
       "segments": [[clip_id, start_s, secs, "English line", cx?], ...], "end": ["…", "…"], "music": ["au-dhak", 0],
       "caption": {"en": "…", "bn": "…", "tags": "…"}},
      {"id": "s1", "type": "story", "at": "10:30", "bn": {"segs": [...]}, "segments": [...]},
      {"id": "b01", "type": "reel", "at": "21:00", "video_url": "https://…", "caption": "…"},   # already rendered
      {"id": "p1", "type": "photo", "at": "08:30", "photos": [{"src", "artist", "license", "cx", "cy"}], "caption": {…}}]}
Photo items are pure photography (no text on the picture), see marketing/footage/photo_post.py.
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

from .. import caption_lint
from ..captions import compose
from ..kit import SITE
from . import photo_post

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


def download(url, dest, tries=5):
    """Wikimedia answers bursts with 429 (and the odd 503): wait and retry rather than fail the whole render."""
    import time
    import urllib.error
    import urllib.parse
    if url.startswith("repo:"):  # a file in this repository (our own app screenshots)
        shutil.copyfile(ROOT / url[5:], dest)
        return
    url = urllib.parse.quote(url, safe=":/?&=%#,()~+'!*;@$")  # a raw non-ASCII path (Bengali file names) can't go on the wire
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=300) as r, open(str(dest) + ".part", "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
            os.replace(str(dest) + ".part", dest)
            return
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or k == tries - 1:
                raise
            wait = int(e.headers.get("Retry-After") or 0) or 5 * 2 ** k
            print(f"{e.code} for {url.rsplit('/', 1)[-1][:60]}, retrying in {wait}s", flush=True)
            time.sleep(min(wait, 120))


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


def speak(text, engine, src_dir):
    """A line with no pre-made file, voiced at render time: engine "edge:<voice>" is Microsoft's neural TTS through
    edge-tts (free; e.g. edge:bn-IN-TanishaaNeural). Used when the house voice has no credits left."""
    kind, voice = engine.split(":", 1)
    if kind != "edge":
        raise SystemExit(f"unknown voice engine {engine}")
    dest = Path(src_dir) / ("vo-" + hashlib.sha1(f"{engine}|{text}".encode()).hexdigest()[:12] + ".mp3")
    if not dest.exists():
        import asyncio
        import edge_tts
        asyncio.run(edge_tts.Communicate(text, voice, rate="-6%", pitch="+2Hz").save(str(dest)))
    return str(dest)


PHOTO_OR_FILM_FROM = "2026-10-11"  # from this day every post is a photograph or footage (no text cards, maps or slides)
TEXT_RENDERS = ("cards", "routes", "cards_reel")  # route reels (animated maps of the app's walks) are allowed again from 10 Oct


FRESH_DAYS = 14  # a photo or clip shown on one day is not shown again for this many days


def visuals(plan):
    """What a plan puts on screen: footage clip ids and photo files (by URL). Music beds are not counted."""
    clips = plan.get("clips") or {}
    seen = set()
    for it in plan.get("items", []):
        for s in it.get("segments") or []:
            seen.add(clips[s[0]]["url"] if s[0] in clips and clips[s[0]].get("url") else s[0])
        for ph in it.get("photos") or []:
            seen.add(ph["src"])
        for sl in it.get("slides") or []:
            if (sl.get("photo") or {}).get("src") and it.get("render") != "editorial":
                seen.add(sl["photo"]["src"])  # editorial slides reuse a topic photo by design (a kalash is a kalash)
    return seen


def repeats(plan, plans_dir=None):
    """Visuals this plan shares with the plans of the previous FRESH_DAYS days."""
    import datetime
    d0 = datetime.date.fromisoformat(plan["date"])
    mine, out = visuals(plan), {}
    for f in sorted(Path(plans_dir or ROOT / "marketing/daily").glob("2*.json")):
        try:
            d = datetime.date.fromisoformat(f.stem)
        except ValueError:
            continue
        if 0 < (d0 - d).days <= FRESH_DAYS:
            for v in mine & visuals(json.load(open(f, encoding="utf-8"))):
                out.setdefault(v, f.stem)
    return out


def check(plan, idx):
    """Every clip exists and every cut fits inside its clip, before anything is downloaded."""
    errs = []
    if plan.get("date", "") >= PHOTO_OR_FILM_FROM:
        for v, d in repeats(plan).items():
            errs.append(f"{v.rsplit('/', 1)[-1][:70]} was already shown on {d}: pick something fresh")
    for it in plan["items"]:
        src_render = {x["id"]: x for x in plan["items"]}.get(it.get("from"), {}).get("render")
        if plan.get("date", "") >= PHOTO_OR_FILM_FROM and it.get("render") in TEXT_RENDERS and src_render != "editorial":
            errs.append(f"{it['id']}: '{it['render']}' is a text/graphic post; use the editorial style (marketing/editorial.py)")
        if it["type"] == "photo":
            errs += photo_post.check(it)
            continue
        if it.get("video_url"):
            continue
        if it.get("render") == "cards_reel":  # a carousel's slides as a reel (marketing/cards_reel.py)
            src = {x["id"]: x for x in plan["items"]}.get(it.get("from"))
            if not (src and src["type"] == "photo" and src["at"] < it["at"] and (it.get("caption") or {}).get("en")):
                errs.append(f"{it['id']}: a cards reel needs an earlier photo post in 'from' and a caption")
            continue
        if it.get("render") == "route":  # animated route reel drawn from the guide (marketing/route_reel.py)
            if not (it.get("zone") and (it.get("caption") or {}).get("en")):
                errs.append(f"{it['id']}: a route reel needs a zone and a caption")
            continue
        for s in it["segments"]:
            e = idx.get(s[0])
            if not e:
                errs.append(f"{it['id']}: unknown clip {s[0]}")
            elif e.get("license") == "used with permission" and not (e.get("permission") and e.get("url")):
                errs.append(f"{it['id']}: {s[0]} ({e['artist']}) has no recorded permission or file yet")
            elif e.get("dur") and s[1] + s[2] > e["dur"] + 0.05:
                errs.append(f"{it['id']}: {s[0]} is {e['dur']}s, cut ends at {s[1] + s[2]}s")
            for a, b, why in e.get("avoid") or [] if e else []:  # stretches of a clip we must not show (footage.json)
                if s[1] < b and s[1] + s[2] > a:
                    errs.append(f"{it['id']}: {s[0]} {s[1]}-{s[1] + s[2]}s overlaps {a}-{b}s ({why})")
        vo = it.get("vo")
        if vo and not (len(vo.get("lines", [])) == len(vo.get("urls") or vo["lines"]) == len(it["segments"])):
            errs.append(f"{it['id']}: voiceover needs one line and one audio url per shot")
        if vo and not vo.get("engine") and not all(vo.get("urls") or []):
            errs.append(f"{it['id']}: a voiceover line has no audio url and no engine to voice it")
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
        if it["type"] == "photo":
            media = "".join(f'<img src="{html.escape(u)}" loading="lazy">' for u in it["image_urls"])
        else:
            media = f'<video src="{html.escape(it["video_url"])}" controls playsinline preload="metadata"></video>'
        notes = ([caption_lint.hook_note(it["hook"])] if it.get("hook") else []) + caption_lint.caption_notes(it.get("caption"))
        lint = "".join(f"<li>{html.escape(n)}</li>" for n in notes if n)
        rows.append(f"""<section><h2>{html.escape(it['at'])} · {it['type']} · {html.escape(it['id'])}</h2>
{media}
<pre>{cap}</pre>{f'<ul class="lint">{lint}</ul>' if lint else ''}</section>""")
    (out / "index.html").write_text(f"""<!doctype html><html lang="bn"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Reels review {date}</title>
<style>body{{font-family:system-ui,sans-serif;background:#fbf3e4;color:#2b1410;margin:0;padding:16px;max-width:760px;margin:auto}}
h1{{color:#b21826}}section{{background:#fff;border:3px solid #b21826;border-radius:14px;padding:12px;margin:16px 0}}
video{{width:100%;max-height:70vh;background:#000;border-radius:8px}}img{{width:100%;border-radius:8px;margin:4px 0}}pre{{white-space:pre-wrap;font:14px/1.45 system-ui}}
.lint{{font-size:13px;color:#7a4a00;background:#fff6dc;border-radius:8px;padding:8px 8px 8px 24px}}</style>
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
    for k, v in (plan.get("clips") or {}).items():  # the day's own clips: AI scenes, stills (source "AI" = not credited by name)
        idx[k] = dict(v, source=v.get("source", "AI"), license=v.get("license", "AI-generated"), artist=v.get("artist", ""),
                      label=v.get("label", k))
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
        if it.get("tags"):  # Instagram accounts to tag on the post (marketing/publish_batch.py)
            entry["tags"] = it["tags"]
        if it.get("hook") and it["type"] == "reel":
            entry["hook"] = it["hook"]
        if it["type"] == "photo":
            names, cap = photo_post.build(it, fid, a.src, out, download)
            entry.update(image_urls=[base + n for n in names], caption=cap)
            print(f"built {fid} photo ×{len(names)}", flush=True)
        elif it.get("video_url"):
            entry.update(video_url=it["video_url"], caption=it.get("caption"))
        elif it.get("render") == "cards_reel":
            from .. import cards_reel
            slides = sorted(out.glob(f"{pfx}-{it['from']}-*.jpg"), key=lambda q: int(q.stem.rsplit("-", 1)[1]))
            mus = it.get("music")  # a licensed bed from the footage index, e.g. ["f22", 30] (Raga Durga)
            secs = cards_reel.render(slides, out / f"{fid}.mp4", tmp,
                                     audio=fetch(mus[0], idx[mus[0]], a.src) if mus else None, start=mus[1] if mus else 2.0)
            cap = compose(it["caption"])
            (out / f"{fid}.caption.txt").write_text(cap + "\n", encoding="utf-8")
            entry.update(video_url=base + f"{fid}.mp4", caption=cap)
            qa_strip(out / f"{fid}.mp4", out / f"qa_{fid}.jpg")
            print(f"built {fid} cards reel from {it['from']} ({len(slides)} slides) {secs:.1f}s", flush=True)
        elif it.get("render") == "route":
            from .. import route_reel
            secs, _ = route_reel.render(it["zone"], out / f"{fid}.mp4")
            cap = route_reel.caption(it["caption"])
            (out / f"{fid}.caption.txt").write_text(cap + "\n", encoding="utf-8")
            entry.update(video_url=base + f"{fid}.mp4", caption=cap)
            qa_strip(out / f"{fid}.mp4", out / f"qa_{fid}.jpg")
            print(f"built {fid} route reel {it['zone']} {secs:.1f}s", flush=True)
        else:
            music = [it["music"]] if it.get("music") and not it.get("vo") else []
            for s in it["segments"] + music + ([it["end_clip"]] if it.get("end_clip") else []):
                fetch(s[0], idx[s[0]], a.src)
            reel = dict(it, id=fid)
            if it.get("vo"):  # voiceover lines, one per shot (generated ahead, see marketing/footage/voice.py)
                vo = it["vo"]
                urls = vo.get("urls") or [None] * len(vo["lines"])
                reel["vo_files"] = [voice_file(u, a.src) if u else speak(t, vo["engine"], a.src) if vo.get("engine") else None
                                    for u, t in zip(urls, vo["lines"])]
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
