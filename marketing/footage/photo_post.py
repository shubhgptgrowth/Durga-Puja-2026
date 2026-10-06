"""Pure-photography posts for the daily set: one full-resolution photograph (or a few, as a carousel), no text on it.

A plan item:
    {"id": "p1", "type": "photo", "at": "08:30",
     "photos": [{"src": "https://upload.wikimedia.org/…jpg", "artist": "…", "license": "CC BY-SA 4.0",
                 "page": "https://commons.wikimedia.org/wiki/File:…", "cx": 0.5, "cy": 0.4}, …],
     "caption": {"bn": "…", "en": "…", "tags": "#… (3 to 5)"}}
Each photo is cropped to Instagram's tallest feed frame (4:5) around (cx, cy) and saved at 1440x1800, Instagram's
largest upload, so nothing is upscaled on its side. The caption ends with the credit each CC licence asks for.
"AI" as the licence marks a generated image: it is not credited by name and the caption says it is AI-made.
"""
import hashlib
from pathlib import Path

PW, PH = 1440, 1800


def check(it):
    errs = []
    ps = it.get("photos") or []
    if not 1 <= len(ps) <= 10:
        errs.append(f"{it['id']}: a photo post needs 1 to 10 photos")
    for p in ps:
        if not p.get("src"):
            errs.append(f"{it['id']}: photo without src")
        elif p.get("license") != "AI" and not (p.get("artist") and p.get("license")):
            errs.append(f"{it['id']}: {p['src'].rsplit('/', 1)[-1]} needs artist and license for the credit")
    c = it.get("caption") or {}
    if not (c.get("bn") or c.get("en")):
        errs.append(f"{it['id']}: a photo post needs a caption")
    return errs


def crop(src, dest, cx=0.5, cy=0.45):
    from PIL import Image, ImageFilter, ImageOps
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    k = max(PW / im.width, PH / im.height)
    w, h = round(PW / k), round(PH / k)  # the 4:5 window in source pixels
    x = min(max(0, round(im.width * cx - w / 2)), im.width - w)
    y = min(max(0, round(im.height * cy - h / 2)), im.height - h)
    im = im.crop((x, y, x + w, y + h)).resize((PW, PH), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=2))
    im.save(dest, quality=93, optimize=True, progressive=True, subsampling=0)
    return min(w / PW, h / PH)  # < 1 means the source was smaller than the frame


def caption(it):
    c = it["caption"]
    real = []
    for p in it["photos"]:
        if p.get("license") != "AI":
            cr = f"{p['artist']} ({p['license']})"
            if cr not in real:
                real.append(cr)
    parts = [c.get("bn", ""), c.get("en", ""), c.get("tags", "")]
    if real:
        parts.append(("📷 Photo: " if len(real) == 1 else "📷 Photos: ") + "; ".join(real) + " · Wikimedia Commons")
    if any(p.get("license") == "AI" for p in it["photos"]):
        parts.append("🤖 AI-generated image.")
    return "\n\n".join(x.strip() for x in parts if x and x.strip())


def build(it, fid, src_dir, out, download):
    """Writes out/<fid>-<n>.jpg and out/<fid>.caption.txt; returns (file names, caption)."""
    names = []
    for n, p in enumerate(it["photos"], 1):
        ext = Path(p["src"].split("?")[0]).suffix.lower() or ".jpg"
        src = Path(src_dir) / ("ph-" + hashlib.sha1(p["src"].encode()).hexdigest()[:12] + ext)
        if not src.exists():
            download(p["src"], src)
        name = f"{fid}-{n}.jpg"
        scale = crop(src, Path(out) / name, p.get("cx", 0.5), p.get("cy", 0.45))
        if scale < 0.75:
            print(f"warning: {fid} photo {n} is upscaled {1 / scale:.1f}x, pick a bigger original", flush=True)
        names.append(name)
    cap = caption(it)
    (Path(out) / f"{fid}.caption.txt").write_text(cap + "\n", encoding="utf-8")
    return names, cap
