"""Editorial carousels: how-tos, mantras, lists and stories from content/knowledge, set like a magazine spread.

A plan item:
    {"id": "p1", "type": "photo", "render": "editorial", "at": "09:30", "caption": {…},
     "slides": [
       {"t": "cover", "kicker": "Navratri · Day 1", "title": "Ghatasthapana at home", "bn": "ঘটস্থাপনা", "sub": "…",
        "photo": {"src": "https://upload.wikimedia.org/…", "artist": "…", "license": "CC BY-SA 4.0", "cx": .5, "cy": .45}},
       {"t": "step", "title": "Prepare the kalash", "bn": "কলস সাজান", "body": "…", "photo": {…}?},
       {"t": "list", "title": "What you need", "items": [["Kalash", "কলস"], "Mango leaves", …]},
       {"t": "mantra", "script": "deva" | "bn", "text": "…", "translit": "…", "meaning": "…", "meaning_bn": "…"},
       {"t": "photo", "photo": {…}, "line": "…"},
       {"t": "end", "title": "Save this for Ashtami morning", "bn": "…", "ask": "Send it to the family group"}]}
Slides are 1440x1800 (Instagram's 4:5 at full size). The look: ivory paper with a sindoor and gold accent for reading
slides, the photograph full-bleed for the cover, deep maroon for mantras. Type: Cormorant Garamond for display,
Marcellus for small caps, Poppins for English body, Tiro Bangla / Hind Siliguri for Bengali, Tiro Devanagari Sanskrit
for Sanskrit. Every photo carries its licence credit in the corner. Fonts come from fonts/ (the render workflow fetches
them); missing faces fall back so a render never fails on a font.
"""
import hashlib
import os
import re
from pathlib import Path

from .captions import compose

W, H = 1440, 1800
M = 120  # page margin
IVORY, PAPER2 = (247, 240, 228), (240, 230, 212)
INK, MUTED = (40, 22, 18), (112, 88, 74)
MAROON, SINDOOR, GOLD = (104, 18, 30), (176, 26, 40), (184, 142, 66)
NIGHT = (44, 10, 12)
HANDLE = "@pujoparikrama.guide"
ROOT = Path(__file__).resolve().parents[1]
FONT_DIRS = [ROOT / "fonts", Path("fonts"), ROOT / "marketing" / "reels" / "fonts"]


def _find(name):
    for d in FONT_DIRS:
        if (d / name).exists():
            return str(d / name)
    return None


_cache = {}


def font(role, size):
    """role → the face for that job, with a fallback chain so a missing file never stops a render."""
    from PIL import ImageFont
    key = (role, size)
    if key in _cache:
        return _cache[key]
    chains = {
        "display": [("CormorantGaramond[wght].ttf", 600), ("Marcellus-Regular.ttf", None), ("Poppins-SemiBold.ttf", None)],
        "display_it": [("CormorantGaramond-Italic[wght].ttf", 500), ("CormorantGaramond[wght].ttf", 500), ("Poppins-Medium.ttf", None)],
        "caps": [("Marcellus-Regular.ttf", None), ("Poppins-SemiBold.ttf", None)],
        "body": [("Poppins-Regular.ttf", None), ("Poppins-Medium.ttf", None)],
        "body_b": [("Poppins-SemiBold.ttf", None), ("Poppins-Bold.ttf", None)],
        "bn": [("TiroBangla-Regular.ttf", None), ("HindSiliguri-Bold.ttf", None)],
        "bn_body": [("HindSiliguri-Regular.ttf", None), ("HindSiliguri-Bold.ttf", None), ("TiroBangla-Regular.ttf", None)],
        "deva": [("TiroDevanagariSanskrit-Regular.ttf", None)],
    }
    raqm = role in ("bn", "bn_body", "deva")
    for name, wght in chains[role]:
        path = _find(name)
        if not path:
            continue
        kw = {"layout_engine": ImageFont.Layout.RAQM} if raqm else {}
        f = ImageFont.truetype(path, size, **kw)
        if wght:
            try:
                f.set_variation_by_axes([wght])
            except (OSError, AttributeError):
                pass
        _cache[key] = f
        return f
    f = ImageFont.load_default(size)
    _cache[key] = f
    return f


def wrap(d, text, f, width):
    words, lines, cur = (text or "").split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def fit(d, text, role, size, width, max_lines, floor=24):
    while size > floor and len(wrap(d, text, font(role, size), width)) > max_lines:
        size -= 2
    return font(role, size)


def draw_lines(d, xy, text, f, fill, width, gap=1.32, align="left", max_lines=99):
    x, y = xy
    for ln in wrap(d, text, f, width)[:max_lines]:
        lx = x if align == "left" else x + (width - d.textlength(ln, font=f)) / 2
        d.text((lx, y), ln, font=f, fill=fill)
        y += round(f.size * gap)
    return y


def spaced(d, xy, text, f, fill, track=0.18, align="left", width=None):
    text = text.upper()
    gap = f.size * track
    tw = sum(d.textlength(c, font=f) for c in text) + gap * (len(text) - 1)
    x, y = xy
    if align == "center":
        x += (width - tw) / 2
    elif align == "right":
        x += width - tw
    for c in text:
        d.text((x, y), c, font=f, fill=fill)
        x += d.textlength(c, font=f) + gap
    return tw


def paper(color=IVORY, seed=7):
    """Warm paper with a faint grain and a soft vignette: reads as print, not a flat fill."""
    from PIL import Image, ImageFilter
    import random
    rnd = random.Random(seed)
    im = Image.new("RGB", (W, H), color)
    noise = Image.effect_noise((W // 2, H // 2), 18).resize((W, H)).filter(ImageFilter.GaussianBlur(0.6))
    im = Image.blend(im, Image.merge("RGB", [noise] * 3), 0.035)
    vig = Image.radial_gradient("L").resize((W, H)).point(lambda v: int(v * 0.35))
    shade = Image.new("RGB", (W, H), tuple(max(0, c - 40) for c in color))
    _ = rnd
    return Image.composite(shade, im, vig)


def photo_img(p, src_dir, download, size, grade=True):
    """The slide's photograph, fetched once, cropped to size around (cx, cy) and graded like the photo posts."""
    from PIL import Image, ImageOps
    from .footage import photo_post
    ext = Path(p["src"].split("?")[0]).suffix.lower() or ".jpg"
    src = Path(src_dir) / ("ph-" + hashlib.sha1(p["src"].encode()).hexdigest()[:12] + ext)
    if not src.exists():
        download(p["src"], src)
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    w, h = size
    k = max(w / im.width, h / im.height)
    cw, ch = round(w / k), round(h / k)
    x = min(max(0, round(im.width * p.get("cx", 0.5) - cw / 2)), im.width - cw)
    y = min(max(0, round(im.height * p.get("cy", 0.45) - ch / 2)), im.height - ch)
    im = im.crop((x, y, x + cw, y + ch)).resize((w, h), Image.LANCZOS)
    return photo_post.grade(im) if grade else im


def credit(d, p, xy_right_bottom, fill=(255, 255, 255, 200)):
    if not p:
        return
    line = "AI image" if p.get("license") == "AI" else f"Photo: {p['artist']} · {p['license']}"
    f = font("body", 20)
    x, y = xy_right_bottom
    d.text((x - d.textlength(line, font=f), y - 26), line, font=f, fill=fill)


def footer(d, k, n, dark=False):
    col = (236, 222, 196) if dark else MUTED
    f = font("caps", 26)
    spaced(d, (M, H - 92), HANDLE.lstrip("@"), f, col, track=0.14)
    if n > 1:
        spaced(d, (W - M - 200, H - 92), f"{k:02d} / {n:02d}", f, col, track=0.14, align="right", width=200)


def header(d, kicker, k, n, dark=False):
    col = GOLD
    f = font("caps", 30)
    spaced(d, (M, 104), kicker or "Pujo Parikrama", f, col, track=0.22)
    d.line((M, 160, W - M, 160), fill=col + (255,) if len(col) == 3 else col, width=2)


def cover(s, k, n, src_dir, download):
    from PIL import Image, ImageDraw
    im = photo_img(s["photo"], src_dir, download, (W, H)) if s.get("photo") else paper(NIGHT)
    shade = Image.new("L", (1, H))
    for y in range(H):
        t = max(0.0, (y - H * 0.34) / (H * 0.66))
        shade.putpixel((0, y), int(235 * t ** 1.15))
    im = Image.composite(Image.new("RGB", (W, H), (22, 6, 8)), im, shade.resize((W, H)))
    top = Image.new("L", (1, 260))
    for y in range(260):
        top.putpixel((0, y), int(120 * (1 - y / 260)))
    im.paste((0, 0, 0), (0, 0, W, 260), top.resize((W, 260)))
    d = ImageDraw.Draw(im, "RGBA")
    spaced(d, (M, 96), s.get("kicker") or "Pujo Parikrama", font("caps", 32), (232, 196, 120), track=0.24)
    ft = fit(d, s["title"], "display", 150, W - 2 * M, 3, floor=90)
    lines = wrap(d, s["title"], ft, W - 2 * M)
    bn = s.get("bn")
    sub = s.get("sub")
    block = len(lines) * round(ft.size * 1.02) + (round(ft.size * 0.28) + 96 if bn else 0) + (120 if sub else 0)
    y = H - 230 - block
    for ln in lines:
        d.text((M, y), ln, font=ft, fill=(252, 246, 236))
        y += round(ft.size * 1.02)
    if bn:
        y += round(ft.size * 0.28)
        y = draw_lines(d, (M, y), bn, fit(d, bn, "bn", 68, W - 2 * M, 1, floor=40), (236, 200, 128), W - 2 * M, max_lines=1)
    if sub:
        y += 10
        draw_lines(d, (M, y), sub, fit(d, sub, "body", 36, W - 2 * M, 2, floor=28), (238, 228, 214), W - 2 * M, max_lines=2)
    d.line((M, H - 140, M + 90, H - 140), fill=SINDOOR, width=6)
    spaced(d, (W - M - 400, H - 156), "Swipe", font("caps", 28), (236, 222, 196), track=0.3, align="right", width=380)
    d.text((W - M - 6, H - 166), "›", font=font("display", 52), fill=(236, 222, 196))
    spaced(d, (M + 120, H - 156), HANDLE.lstrip("@"), font("caps", 26), (236, 222, 196), track=0.14)
    credit(d, s.get("photo"), (W - 40, H - 30))
    return im


def step(s, k, n, src_dir, download):
    from PIL import Image, ImageDraw
    has_photo = bool(s.get("photo"))
    body = s.get("body") or ""

    def lay(d, y0):
        y = y0
        if s.get("num") is not None:  # the step number, large and faint, top right of the title
            fn = font("display", 260)
            num = f"{s['num']:02d}" if isinstance(s["num"], int) else str(s["num"])
            d.text((W - M - d.textlength(num, font=fn), y - 120), num, font=fn, fill=GOLD + (70,))
        ft = fit(d, s["title"], "display", 112, W - 2 * M - (260 if s.get("num") is not None else 0), 2, floor=72)
        y = draw_lines(d, (M, y), s["title"], ft, MAROON, W - 2 * M, gap=1.04, max_lines=2)
        if s.get("bn"):
            y += round(ft.size * 0.3)
            fb_ = fit(d, s["bn"], "bn", 58, W - 2 * M, 1, floor=40)
            y = draw_lines(d, (M, y), s["bn"], fb_, SINDOOR, W - 2 * M, gap=1.3, max_lines=1)
        y += 34
        d.line((M, y, M + 120, y), fill=SINDOOR, width=5)
        y += 54
        limit = (H - 180 - 620 - 40) if has_photo else (H - 200)
        fb = font("body", 48 if not has_photo else 42)
        while fb.size > 30 and y + len(wrap(d, body, fb, W - 2 * M)) * round(fb.size * 1.5) > limit:
            fb = font("body", fb.size - 2)
        y = draw_lines(d, (M, y), body, fb, INK, W - 2 * M, gap=1.5)
        if s.get("bn_body"):
            y += 22
            y = draw_lines(d, (M, y), s["bn_body"], fit(d, s["bn_body"], "bn_body", 42, W - 2 * M, 3, floor=30), MUTED,
                           W - 2 * M, gap=1.45, max_lines=3)
        return y

    if has_photo:
        im = paper()
        d = ImageDraw.Draw(im, "RGBA")
        lay(d, 300)
    else:
        im, d = centred(lay, 330, H - 200, paper)
    header(d, s.get("kicker"), k, n)
    if has_photo:
        ph = photo_img(s["photo"], src_dir, download, (W - 2 * M, 620))
        mask = Image.new("L", ph.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, ph.width, ph.height), 28, fill=255)
        im.paste(ph, (M, H - 180 - 620), mask)
        d = ImageDraw.Draw(im, "RGBA")
        credit(d, s["photo"], (W - M - 18, H - 180 - 14))
    footer(d, k, n)
    return im


def listing(s, k, n, src_dir, download):
    items = [it if isinstance(it, (list, tuple)) else [it, ""] for it in s["items"]]
    cols = 2 if len(items) > 6 else 1
    colw = (W - 2 * M - (70 if cols == 2 else 0)) // cols
    per = -(-len(items) // cols)

    def lay(d, y0):
        y = y0
        ft = fit(d, s["title"], "display", 112, W - 2 * M, 2, floor=70)
        y = draw_lines(d, (M, y), s["title"], ft, MAROON, W - 2 * M, gap=1.04, max_lines=2)
        if s.get("bn"):
            y += round(ft.size * 0.22)
            y = draw_lines(d, (M, y), s["bn"], fit(d, s["bn"], "bn", 56, W - 2 * M, 1, floor=38), SINDOOR, W - 2 * M, max_lines=1)
        y += 64
        avail = H - 210 - y
        fe = font("body", 46 if cols == 1 else 42)
        def height(f):
            fbn = font("bn_body", max(26, f.size - 8))
            return max(sum(len(wrap(d, a, f, colw - 56)) * round(f.size * 1.3) + (round(fbn.size * 1.45) if b else 0) + 30
                           for a, b in items[c * per:(c + 1) * per]) for c in range(cols))
        while fe.size > 28 and height(fe) > avail:
            fe = font("body", fe.size - 2)
        fbn = font("bn_body", max(26, fe.size - 8))
        bottom = y
        for c in range(cols):
            x, yy = M + c * (colw + 70), y
            for a, b in items[c * per:(c + 1) * per]:
                cy = yy + fe.size * 0.66
                d.polygon([(x + 9, cy - 10), (x + 19, cy), (x + 9, cy + 10), (x - 1, cy)], fill=GOLD)
                yy = draw_lines(d, (x + 50, yy), a, fe, INK, colw - 56, gap=1.3)
                if b:
                    yy = draw_lines(d, (x + 50, yy + 2), b, fbn, MUTED, colw - 56, gap=1.3, max_lines=1)
                yy += 30
            bottom = max(bottom, yy)
        return bottom

    im, d = centred(lay, 250, H - 200, paper)
    header(d, s.get("kicker"), k, n)
    footer(d, k, n)
    return im


def mantra(s, k, n, src_dir, download):
    from PIL import Image

    def bg():
        im = paper(NIGHT, seed=3)
        glow = Image.radial_gradient("L").resize((W, H)).point(lambda v: int(80 * (1 - v / 255) ** 2))
        return Image.composite(Image.new("RGB", (W, H), (124, 32, 30)), im, glow)

    role = "deva" if s.get("script", "deva") == "deva" else "bn"
    lines_src = [ln.strip() for ln in s["text"].split("\n") if ln.strip()]

    def lay(d, y0):
        y = y0
        ftx = font(role, 86)
        while ftx.size > 44 and sum(len(wrap(d, ln, ftx, W - 2 * M)) for ln in lines_src) * round(ftx.size * 1.6) > 760:
            ftx = font(role, ftx.size - 2)
        for ln in lines_src:
            y = draw_lines(d, (M, y), ln, ftx, (252, 240, 214), W - 2 * M, gap=1.6, align="center")
        y += 30
        if s.get("translit"):
            fi = fit(d, s["translit"], "display_it", 54, W - 2 * M, 4, floor=36)
            y = draw_lines(d, (M, y), s["translit"], fi, (226, 190, 120), W - 2 * M, gap=1.28, align="center")
        y += 46
        cx = W // 2
        d.polygon([(cx, y - 11), (cx + 11, y), (cx, y + 11), (cx - 11, y)], fill=GOLD)
        d.line((cx - 180, y, cx - 30, y), fill=GOLD, width=2)
        d.line((cx + 30, y, cx + 180, y), fill=GOLD, width=2)
        y += 58
        if s.get("meaning"):
            fm = fit(d, s["meaning"], "body", 44, W - 2 * M, 6, floor=30)
            y = draw_lines(d, (M, y), s["meaning"], fm, (240, 228, 210), W - 2 * M, gap=1.5, align="center")
        if s.get("meaning_bn"):
            y += 22
            y = draw_lines(d, (M, y), s["meaning_bn"], fit(d, s["meaning_bn"], "bn_body", 42, W - 2 * M, 3, floor=28),
                           (214, 186, 150), W - 2 * M, gap=1.45, align="center", max_lines=3)
        return y

    im, d = centred(lay, 230, H - 190, bg)
    spaced(d, (M, 104), s.get("kicker") or "Mantra", font("caps", 30), GOLD, track=0.22)
    d.line((M, 160, W - M, 160), fill=GOLD, width=2)
    footer(d, k, n, dark=True)
    return im


def photo_slide(s, k, n, src_dir, download):
    from PIL import Image, ImageDraw
    im = photo_img(s["photo"], src_dir, download, (W, H))
    if s.get("line"):
        shade = Image.new("L", (1, 520))
        for y in range(520):
            shade.putpixel((0, y), int(210 * (y / 520) ** 1.2))
        im.paste((20, 6, 8), (0, H - 520, W, H), shade.resize((W, 520)))
    d = ImageDraw.Draw(im, "RGBA")
    if s.get("line"):
        f = fit(d, s["line"], "display_it", 64, W - 2 * M, 3, floor=40)
        n_lines = len(wrap(d, s["line"], f, W - 2 * M))
        draw_lines(d, (M, H - 200 - n_lines * round(f.size * 1.15)), s["line"], f, (252, 244, 230), W - 2 * M, gap=1.15)
    credit(d, s["photo"], (W - 40, H - 30))
    footer(d, k, n, dark=True)
    return im


def end(s, k, n, src_dir, download):
    from PIL import ImageDraw
    im = paper()
    d = ImageDraw.Draw(im, "RGBA")
    cx = W // 2
    d.ellipse((cx - 70, 300, cx + 70, 440), outline=SINDOOR, width=5)
    d.ellipse((cx - 22, 348, cx + 22, 392), fill=SINDOOR)
    y = 540
    ft = fit(d, s["title"], "display", 120, W - 2 * M, 3, floor=70)
    y = draw_lines(d, (M, y), s["title"], ft, MAROON, W - 2 * M, gap=1.06, align="center")
    if s.get("bn"):
        y = draw_lines(d, (M, y + round(ft.size * 0.3)), s["bn"], fit(d, s["bn"], "bn", 56, W - 2 * M, 2, floor=36), SINDOOR, W - 2 * M,
                       gap=1.35, align="center", max_lines=2)
    y += 60
    ask = s.get("ask") or "Save it · send it to the family group"
    fa = fit(d, ask, "body_b", 36, W - 2 * M - 120, 1, floor=26)
    tw = d.textlength(ask, font=fa)
    d.rounded_rectangle((cx - tw / 2 - 50, y, cx + tw / 2 + 50, y + 96), 48, fill=MAROON)
    d.text((cx - tw / 2, y + 48 - fa.size * 0.62), ask, font=fa, fill=IVORY)
    y += 170
    spaced(d, (M, y), "Free pandal guide · link in bio", font("caps", 30), MUTED, track=0.16, align="center", width=W - 2 * M)
    spaced(d, (M, y + 56), HANDLE.lstrip("@"), font("caps", 30), GOLD, track=0.2, align="center", width=W - 2 * M)
    return im


def centred(draw_fn, top, bottom, bg_fn):
    """Lays a slide's text block out once on scratch paper to measure it, then again centred between top and bottom."""
    from PIL import ImageDraw
    scratch = bg_fn()
    end_y = draw_fn(ImageDraw.Draw(scratch, "RGBA"), 0)
    im = bg_fn()
    d = ImageDraw.Draw(im, "RGBA")
    off = max(top, top + (bottom - top - end_y) // 2)
    draw_fn(d, off)
    return im, d


KINDS = {"cover": cover, "step": step, "list": listing, "mantra": mantra, "photo": photo_slide, "end": end}


def check(it):
    errs = []
    sl = it.get("slides") or []
    if not 2 <= len(sl) <= 10:
        errs.append(f"{it['id']}: an editorial carousel needs 2 to 10 slides")
    for i, s in enumerate(sl, 1):
        if s.get("t") not in KINDS:
            errs.append(f"{it['id']}: slide {i} has unknown kind {s.get('t')!r}")
        for p in [s.get("photo")] if s.get("photo") else []:
            if p.get("license") != "AI" and not (p.get("artist") and p.get("license") and p.get("src")):
                errs.append(f"{it['id']}: slide {i} photo needs src, artist and license")
        if s.get("t") == "mantra" and not (s.get("text") and s.get("meaning")):
            errs.append(f"{it['id']}: slide {i} mantra needs text and meaning")
    if not (it.get("caption") or {}).get("en"):
        errs.append(f"{it['id']}: needs a caption")
    return errs


def build(it, fid, src_dir, out, download):
    """Writes out/<fid>-<n>.jpg and out/<fid>.caption.txt; returns (file names, caption)."""
    sl = it["slides"]
    names = []
    for k, s in enumerate(sl, 1):
        im = KINDS[s["t"]](s, k, len(sl), src_dir, download).convert("RGB")
        name = f"{fid}-{k}.jpg"
        im.save(Path(out) / name, quality=93, optimize=True, progressive=True, subsampling=0)
        names.append(name)
    cap = compose(it["caption"])
    (Path(out) / f"{fid}.caption.txt").write_text(cap + "\n", encoding="utf-8")
    return names, cap
