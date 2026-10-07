"""Pure-photography posts for the daily set: one full-resolution photograph (or a few, as a carousel), no text on it.

A plan item:
    {"id": "p1", "type": "photo", "at": "08:30",
     "photos": [{"src": "https://upload.wikimedia.org/…jpg", "artist": "…", "license": "CC BY-SA 4.0",
                 "page": "https://commons.wikimedia.org/wiki/File:…", "cx": 0.5, "cy": 0.4}, …],
     "caption": {"en": "…", "keywords": [...], "tags": "#… (up to 3)"}}   # layout: marketing/captions.py
Each photo is cropped to Instagram's tallest feed frame (4:5) around (cx, cy) and saved at 1440x1800, Instagram's
largest upload, so nothing is upscaled on its side. The credit each CC licence asks for is printed small in the
photo's bottom corner, not in the caption. "AI" as the licence marks a generated image, labelled "AI image" there.
"""
import hashlib
from pathlib import Path

from ..captions import compose

PW, PH = 1440, 1800


def check(it):
    errs = []
    if it.get("render") == "routes":
        return [] if (it.get("caption") or {}).get("en") else [f"{it['id']}: a route carousel needs a caption"]
    ps = it.get("photos") or []
    if not 1 <= len(ps) <= 10:
        errs.append(f"{it['id']}: a photo post needs 1 to 10 photos")
    for p in ps:
        if not p.get("src"):
            errs.append(f"{it['id']}: photo without src")
        elif p.get("license") != "AI" and not (p.get("artist") and p.get("license")):
            errs.append(f"{it['id']}: {p['src'].rsplit('/', 1)[-1]} needs artist and license for the credit")
    c = it.get("caption") or {}
    if not c.get("en"):
        errs.append(f"{it['id']}: a photo post needs a caption")
    return errs


def credit_line(p):
    return "AI image" if p.get("license") == "AI" else f"Photo: {p['artist']} · {p['license']}"


def stamp(im, line):
    """The licence credit, small and low in the corner: legible when zoomed, out of the way in the feed."""
    from PIL import ImageDraw
    from ..routes import F  # Poppins from the repo's font dirs, DejaVu when it isn't there
    d = ImageDraw.Draw(im, "RGBA")
    f = F("med", 22)
    w = d.textlength(line, font=f)
    x, y = im.width - w - 26, im.height - 44
    d.rounded_rectangle((x - 12, y - 6, x + w + 12, y + 30), 10, fill=(0, 0, 0, 110))
    d.text((x, y), line, font=f, fill=(255, 255, 255, 215))


def crop(src, dest, cx=0.5, cy=0.45, credit=None):
    from PIL import Image, ImageFilter, ImageOps
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    k = max(PW / im.width, PH / im.height)
    w, h = round(PW / k), round(PH / k)  # the 4:5 window in source pixels
    x = min(max(0, round(im.width * cx - w / 2)), im.width - w)
    y = min(max(0, round(im.height * cy - h / 2)), im.height - h)
    im = im.crop((x, y, x + w, y + h)).resize((PW, PH), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=2))
    if credit:
        stamp(im, credit)
    im.save(dest, quality=93, optimize=True, progressive=True, subsampling=0)
    return min(w / PW, h / PH)  # < 1 means the source was smaller than the frame


def caption(it):
    return compose(it["caption"])


def build_routes(it, fid, src_dir, out):
    """{"render": "routes", "zones": [...]}: the area-wise route carousel drawn from the guide (marketing/routes.py)."""
    import shutil
    from .. import routes
    tmp = Path(out) / "_routes"
    n, credits = routes.build(tmp, it.get("zones"), cache=str(Path(src_dir) / "routes"))
    names = []
    for k in range(1, n + 1):
        name = f"{fid}-{k}.jpg"
        shutil.copy(tmp / f"slide-{k:02d}.jpg", Path(out) / name)
        names.append(name)
    shutil.rmtree(tmp, ignore_errors=True)
    cap = compose(it["caption"])
    (Path(out) / f"{fid}.caption.txt").write_text(cap + "\n", encoding="utf-8")
    return names, cap


def build(it, fid, src_dir, out, download):
    """Writes out/<fid>-<n>.jpg and out/<fid>.caption.txt; returns (file names, caption)."""
    if it.get("render") == "routes":
        return build_routes(it, fid, src_dir, out)
    names = []
    for n, p in enumerate(it["photos"], 1):
        ext = Path(p["src"].split("?")[0]).suffix.lower() or ".jpg"
        src = Path(src_dir) / ("ph-" + hashlib.sha1(p["src"].encode()).hexdigest()[:12] + ext)
        if not src.exists():
            download(p["src"], src)
        name = f"{fid}-{n}.jpg"
        scale = crop(src, Path(out) / name, p.get("cx", 0.5), p.get("cy", 0.45), credit_line(p))
        if scale < 0.75:
            print(f"warning: {fid} photo {n} is upscaled {1 / scale:.1f}x, pick a bigger original", flush=True)
        names.append(name)
    cap = caption(it)
    (Path(out) / f"{fid}.caption.txt").write_text(cap + "\n", encoding="utf-8")
    return names, cap
