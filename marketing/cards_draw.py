"""Drawing for marketing/cards.py (needs Pillow)."""
from pathlib import Path

from PIL import Image, ImageDraw

from .routes import F, INK, WHITE, YEL, W, H, cover_fit, fit, text, wrap

BG = (16, 10, 8)
RED = (178, 24, 38)
HANDLE = "@pujoparikrama.guide"


def lines(x):
    return x if isinstance(x, list) else [x]


def credit(d, p):
    line = "AI image" if p.get("license") == "AI" else f"Photo: {p['artist']} · {p['license']}"
    f = F("med", 22)
    w = d.textlength(line, font=f)
    x, y = W - w - 30, H - 46
    d.rounded_rectangle((x - 12, y - 6, x + w + 12, y + 30), 10, fill=(0, 0, 0, 120))
    d.text((x, y), line, font=f, fill=(255, 255, 255, 215))


def backdrop(s, photo_path, dark):
    if photo_path:
        p = s["photo"]
        im = cover_fit(Image.open(photo_path), W, H, p.get("cy", 0.42))
        im = Image.blend(im, Image.new("RGB", (W, H), (0, 0, 0)), dark)
        grad = Image.linear_gradient("L").resize((W, H))  # darker at the foot, where the words sit
        return Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), im, grad.point(lambda v: int(v * 0.6)))
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 22), fill=RED)  # laal-paar edge, like the end cards
    d.rectangle((0, 22, W, 30), fill=YEL)
    return im


def block(d, y, s, f, width, fill=WHITE, gap=1.18, anchor_x=90, centre=False, stroke=0, max_lines=6):
    for ln in wrap(d, s, f, width)[:max_lines]:
        if centre:
            text(d, (W // 2, y), ln, f, fill=fill, anchor="ma", stroke=stroke)
        else:
            text(d, (anchor_x, y), ln, f, fill=fill, stroke=stroke)
        y += int(f.size * gap)
    return y


def big_lines(d, ls, size, width):
    while size > 70 and max(d.textlength(l.upper(), font=F("display", size)) for l in ls) > width:
        size -= 6
    return F("display", size)


def cover(s, photo):
    im = backdrop(s, photo, 0.35 if photo else 0)
    d = ImageDraw.Draw(im, "RGBA")
    text(d, (W // 2, 90), HANDLE, F("semi", 38), anchor="mm", stroke=2)
    ls = [l.upper() for l in lines(s["title"])]
    f = big_lines(d, ls, 170, W - 140)
    y = H - 260 - len(ls) * int(f.size * 1.05) - (120 if s.get("sub") else 0)
    if s.get("kicker"):
        text(d, (W // 2, y - 70), s["kicker"].upper(), F("semi", 40), fill=YEL, anchor="mm", stroke=2)
    for ln in ls:
        text(d, (W // 2, y), ln, f, fill=YEL, anchor="ma", stroke=4)
        bottom = d.textbbox((W // 2, y), ln, font=f, anchor="ma", stroke_width=4)[3]
        y = max(y + int(f.size * 1.05), bottom + 8)
    if s.get("sub"):
        y = block(d, bottom + 40, s["sub"], F("semi", 50), W - 200, centre=True, stroke=3, max_lines=2)
    if s.get("pill"):
        fp = F("bold", 44)
        tw = d.textlength(s["pill"], font=fp)
        d.rounded_rectangle((W // 2 - tw / 2 - 50, y + 30, W // 2 + tw / 2 + 50, y + 120), 45, fill=YEL)
        text(d, (W // 2, y + 75), s["pill"], fp, fill=INK, anchor="mm")
    if photo:
        credit(d, s["photo"])
    return im


def item(s, photo):
    im = backdrop(s, photo, 0.62 if photo else 0)
    d = ImageDraw.Draw(im, "RGBA")
    y = 200
    if s.get("kicker"):
        text(d, (90, y), s["kicker"].upper(), F("semi", 44), fill=YEL)
        y += 90
    if s.get("name"):
        y = block(d, y, s["name"], F("bold", 76), W - 180, max_lines=2) + 40
    size = 170
    while size > 80 and len(wrap(d, s["title"].upper(), F("display", size), W - 180)) > 3:
        size -= 8  # the whole title, in at most three lines
    f = F("display", size)
    bottom = y
    for ln in wrap(d, s["title"].upper(), f, W - 180):
        text(d, (90, y), ln, f, fill=YEL, stroke=2)
        bottom = d.textbbox((90, y), ln, font=f, stroke_width=2)[3]  # Anton draws well below its line step
        y = bottom + int(f.size * 0.12)
    d.rectangle((90, bottom + 36, 330, bottom + 44), fill=RED)
    if s.get("body"):
        block(d, bottom + 90, s["body"], F("med", 58), W - 180, max_lines=7)
    if s.get("foot"):
        d.rounded_rectangle((70, H - 250, W - 70, H - 90), 34, fill=(255, 255, 255, 28))
        text(d, (110, H - 170), s["foot"], fit(d, s["foot"], "semi", 44, W - 220), fill=WHITE, anchor="lm")
    text(d, (W - 90, 90), HANDLE, F("med", 28), fill=(200, 200, 200), anchor="ra")
    if photo:
        credit(d, s["photo"])
    return im


def photo_slide(s, photo):
    im = backdrop(s, photo, 0.18)
    d = ImageDraw.Draw(im, "RGBA")
    body = wrap(d, s.get("body", ""), F("med", 46), W - 180)[:5] if s.get("body") else []
    f = F("display", 120)
    tl = wrap(d, s["title"].upper(), f, W - 180)[:3]
    y = H - 160 - len(body) * 56 - len(tl) * 124 - (70 if s.get("kicker") else 0)
    if s.get("kicker"):
        text(d, (90, y), s["kicker"].upper(), F("semi", 40), fill=YEL, stroke=2)
        y += 70
    for ln in tl:
        text(d, (90, y), ln, f, fill=WHITE, stroke=3)
        y += 124
    y += 24
    for ln in body:
        text(d, (90, y), ln, F("med", 46), stroke=2)
        y += 56
    credit(d, s["photo"])
    return im


def end(s, photo):
    im = backdrop(s, photo, 0.55 if photo else 0)
    d = ImageDraw.Draw(im, "RGBA")
    ls = [l.upper() for l in lines(s["title"])]
    f = big_lines(d, ls, 190, W - 140)
    y = 560
    for k, ln in enumerate(ls):
        text(d, (W // 2, y), ln, f, fill=YEL if k == len(ls) - 1 else WHITE, anchor="ma", stroke=4)
        bottom = d.textbbox((W // 2, y), ln, font=f, anchor="ma", stroke_width=4)[3]
        y = max(y + int(f.size * 1.05), bottom + 8)
    if s.get("sub"):
        y = block(d, bottom + 50, s["sub"], F("semi", 52), W - 220, centre=True, stroke=3, max_lines=3)
    if s.get("pill"):
        fp = F("bold", 44)
        tw = d.textlength(s["pill"], font=fp)
        d.rounded_rectangle((W // 2 - tw / 2 - 50, y + 60, W // 2 + tw / 2 + 50, y + 150), 45, fill=YEL)
        text(d, (W // 2, y + 105), s["pill"], fp, fill=INK, anchor="mm")
    text(d, (W // 2, H - 160), HANDLE, F("semi", 44), anchor="mm", stroke=2)
    if photo:
        credit(d, s["photo"])
    return im


DRAW = {"cover": cover, "item": item, "photo": photo_slide, "end": end}


def build(it, fid, src_dir, out, download):
    """Writes out/<fid>-<n>.jpg for each slide; returns the file names."""
    import hashlib
    names = []
    for n, s in enumerate(it["slides"], 1):
        path = None
        if s.get("photo"):
            src = s["photo"]["src"]
            ext = Path(src.split("?")[0]).suffix.lower() or ".jpg"
            path = Path(src_dir) / ("ph-" + hashlib.sha1(src.encode()).hexdigest()[:12] + ext)
            if not path.exists():
                download(src, path)
        im = DRAW[s["t"]](s, path)
        name = f"{fid}-{n}.jpg"
        im.convert("RGB").save(Path(out) / name, quality=92, optimize=True, progressive=True)
        names.append(name)
    return names
