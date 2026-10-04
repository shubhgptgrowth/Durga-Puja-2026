"""Bengali-first Instagram posts and stories in the "laal-paar" look: real photos or Kalighat-pat art, a red-and-gold
sari border, Bengali calligraphy first and English second.

    python3 design.py spec4.json footage3.json src out [post_id,...]

spec4.json  {"art": {kN: url}, "posts": [{"id", "size": "post"|"story", "slides": [{"t": template, ...}], "caption": {...}}]}
footage3.json  photo id -> {license, artist, ...}; photos are src/<pNNN>.jpg, illustrations src/<kN>.png.
Templates: word, cover, pat, versus, list, cta, bingo, prompt, story. Needs Pillow with raqm (Bengali shaping) and
the fonts in ./fonts (see run4.sh).
"""
import json, os, random, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, features

if not features.check("raqm"):
    raise SystemExit("Pillow needs raqm to shape Bengali text")

W = 1080
SIZES = {"post": (1080, 1350), "story": (1080, 1920)}
RED, GOLD, CREAM, INK, MAROON = (179, 18, 46), (232, 176, 75), (255, 244, 224), (58, 34, 22), (122, 16, 32)
HANDLE, BRAND_BN = "@pujoparikrama.guide", "পুজো পরিক্রমা"
FONT = {
    "callig": "Galada-Regular.ttf", "bn": "TiroBangla-Regular.ttf", "bn_b": "HindSiliguri-Bold.ttf",
    "bn_m": "HindSiliguri-SemiBold.ttf", "serif_i": "DMSerifDisplay-Italic.ttf", "serif": "DMSerifDisplay-Regular.ttf",
    "en": "HindSiliguri-Medium.ttf", "en_b": "Poppins-SemiBold.ttf",
}
_cache = {}


def font(kind, size):
    k = (kind, size)
    if k not in _cache:
        _cache[k] = ImageFont.truetype(os.path.join("fonts", FONT[kind]), size, layout_engine=ImageFont.Layout.RAQM)
    return _cache[k]


def wrap(d, text, f, width):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for w in para.split():
            t = (cur + " " + w).strip()
            if d.textlength(t, font=f) <= width or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def text_block(d, xy, text, f, fill, width, lh=1.25, align="left", shadow=None, max_lines=None):
    """Draws wrapped text and returns the y below it. align: left|center."""
    x, y = xy
    lines = wrap(d, text, f, width)
    if max_lines:
        lines = lines[:max_lines]
    for ln in lines:
        tx = x + (width - d.textlength(ln, font=f)) / 2 if align == "center" else x
        if shadow:
            d.text((tx + 3, y + 4), ln, font=f, fill=shadow)
        d.text((tx, y), ln, font=f, fill=fill)
        y += int(f.size * lh)
    return y


def fit_font(d, text, kind, size, width, min_size, max_lines=2):
    while size > min_size and len(wrap(d, text, font(kind, size), width)) > max_lines:
        size -= 4
    return font(kind, size)


def paper(size, seed=7):
    """Cream handmade-paper background with grain and a soft vignette."""
    w, h = size
    rnd = random.Random(seed)
    base = Image.new("RGB", (w // 4, h // 4), CREAM)
    px = base.load()
    for yy in range(base.height):
        for xx in range(base.width):
            n = rnd.randint(-10, 6)
            r, g, b = CREAM
            px[xx, yy] = (r + n, g + n, b + n - 4)
    base = base.resize(size, Image.BICUBIC).filter(ImageFilter.GaussianBlur(1.2))
    vig = Image.new("L", size, 0)
    ImageDraw.Draw(vig).ellipse((-w * 0.25, -h * 0.2, w * 1.25, h * 1.2), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(160))
    dark = Image.new("RGB", size, (214, 190, 150))
    return Image.composite(base, dark, vig)


def cover_crop(im, size, cx=0.5, cy=0.45):
    im = ImageOps.exif_transpose(im).convert("RGB")
    w, h = size
    k = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    x = min(max(0, round(im.width * cx - w / 2)), im.width - w)
    y = min(max(0, round(im.height * cy - h / 2)), im.height - h)
    im = im.crop((x, y, x + w, y + h))
    # warm, slightly filmic grade
    im = Image.blend(im, Image.new("RGB", size, (60, 30, 10)), 0.06)
    return ImageOps.autocontrast(im, cutoff=0.5)


def gradient(size, top=0, bottom=235, start=0.35, color=(30, 6, 8)):
    """Transparent → colour from `start` (fraction of height) to the bottom; top>0 also darkens the top band."""
    w, h = size
    g = Image.new("L", (1, h))
    for y in range(h):
        t = y / h
        a = 0
        if t > start:
            a = bottom * ((t - start) / (1 - start)) ** 1.3
        if top and t < 0.3:
            a = max(a, top * (1 - t / 0.3) ** 1.5)
        g.putpixel((0, y), int(a))
    layer = Image.new("RGBA", size, color + (0,))
    layer.putalpha(g.resize(size))
    return layer


def border(im):
    """The laal-paar: a red sari border with a thin gold line inside it."""
    d = ImageDraw.Draw(im)
    w, h = im.size
    d.rectangle((0, 0, w - 1, h - 1), outline=RED, width=26)
    d.rectangle((30, 30, w - 31, h - 31), outline=GOLD, width=3)
    # small alpona dots along the border
    for x in range(70, w - 40, 60):
        for y in (13, h - 14):
            d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=CREAM)
    return im


def alpona(d, cx, cy, r, color, petals=12):
    """A simple alpona rosette: petals around concentric rings."""
    import math
    for k in range(petals):
        a = 2 * math.pi * k / petals
        px, py = cx + r * math.cos(a), cy + r * math.sin(a)
        d.ellipse((px - r * 0.28, py - r * 0.28, px + r * 0.28, py + r * 0.28), outline=color, width=3)
    d.ellipse((cx - r * 0.55, cy - r * 0.55, cx + r * 0.55, cy + r * 0.55), outline=color, width=3)
    d.ellipse((cx - r * 0.18, cy - r * 0.18, cx + r * 0.18, cy + r * 0.18), fill=color)


def panel(im, box, color, alpha):
    """A translucent rounded panel behind text, so it stays readable over busy photos or drawings."""
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius=26, fill=color + (alpha,))
    return Image.alpha_composite(im.convert("RGBA"), layer).convert("RGB")


def brand(d, size, dark_bg=True, page=None):
    fill = CREAM if dark_bg else MAROON
    d.text((66, 58), BRAND_BN, font=font("callig", 46), fill=fill)
    if page:
        f = font("en_b", 26)
        t = f"{page[0]} / {page[1]}"
        tw = d.textlength(t, font=f)
        d.rounded_rectangle((size[0] - 66 - tw - 36, 62, size[0] - 66, 108), radius=23, outline=fill, width=3)
        d.text((size[0] - 66 - tw - 18, 68), t, font=f, fill=fill)


def footer(d, size, dark_bg=True, credit=""):
    fill = CREAM if dark_bg else MAROON
    w, h = size
    d.text((66, h - 108), HANDLE, font=font("en_b", 30), fill=fill)
    if credit:
        f = font("en", 20)
        tw = d.textlength(credit, font=f)
        d.text((w - 66 - tw, h - 100), credit, font=f, fill=fill + (200,) if len(fill) == 3 else fill)


def load(src_dir, ref):
    for ext in (".jpg", ".png"):
        p = os.path.join(src_dir, ref + ext)
        if os.path.exists(p):
            return Image.open(p)
    raise SystemExit(f"missing image {ref}")


def credit_of(ref, footage):
    if ref.startswith("k"):
        return "Illustration: AI, Kalighat pat style"
    f = footage[ref]
    return f"Photo: {f['artist']} · {f['license']} · Wikimedia Commons"


# ---------- templates ----------

def t_word(s, size, src, footage, page):
    """Full-bleed photo, a big Bengali word, transliteration, English meaning."""
    im = cover_crop(load(src, s["img"]), size, s.get("cx", 0.5), s.get("cy", 0.45))
    im = Image.alpha_composite(im.convert("RGBA"), gradient(size, top=150, start=0.32)).convert("RGB")
    d = ImageDraw.Draw(im)
    w, h = size
    f = fit_font(d, s["bn"], "callig", 150, w - 140, 84, max_lines=2)
    fe = font("en", 38)
    block = len(wrap(d, s["bn"], f, w - 140)) * int(f.size * 1.12) + 86 + len(wrap(d, s["en"], fe, w - 150)) * int(38 * 1.35)
    y = h - 150 - block
    y = text_block(d, (70, y), s["bn"], f, CREAM, w - 140, lh=1.12, shadow=(0, 0, 0))
    y += 6
    d.text((72, y), s["tr"], font=font("serif_i", 52), fill=GOLD)
    y += 80
    text_block(d, (72, y), s["en"], fe, (255, 236, 220), w - 150, lh=1.35)
    brand(d, size, True, page)
    footer(d, size, True, credit_of(s["img"], footage))
    return border(im)


def t_cover(s, size, src, footage, page):
    if s.get("img"):
        im = cover_crop(load(src, s["img"]), size, s.get("cx", 0.5), s.get("cy", 0.45))
        im = Image.alpha_composite(im.convert("RGBA"), gradient(size, top=120, start=0.25, bottom=245)).convert("RGB")
        dark, ink, sub = True, CREAM, GOLD
    else:
        im = paper(size)
        dark, ink, sub = False, MAROON, INK
    d = ImageDraw.Draw(im)
    w, h = size
    if s.get("grid"):  # 2×2 thumbnails of the carousel's illustrations
        tw, th = 300, 375 if h > 1350 else 330
        x0 = (w - 2 * tw - 30) // 2
        for i, ref in enumerate(s["grid"][:4]):
            t = cover_crop(load(src, ref), (tw, th), 0.5, 0.6)
            x, y0 = x0 + (i % 2) * (tw + 30), 140 + (i // 2) * (th + 22)
            im.paste(t, (x, y0))
            d.rectangle((x - 4, y0 - 4, x + tw + 3, y0 + th + 3), outline=RED, width=4)
        y = 140 + 2 * (th + 22) + 6
    else:
        y = h - 620 if size[1] == 1350 else h - 860
    if s.get("kicker"):
        d.text((72, y), s["kicker"], font=font("en_b", 30), fill=sub)
        y += 56
    f = fit_font(d, s["bn"], "callig", 140, w - 140, 80, max_lines=2)
    y = text_block(d, (70, y), s["bn"], f, ink, w - 140, lh=1.12, shadow=(0, 0, 0) if dark else None)
    if s.get("bn2"):
        y = text_block(d, (72, y + 4), s["bn2"], font("bn_m", 50), ink, w - 150, lh=1.3)
    if s.get("en"):
        y = text_block(d, (72, y + 14), s["en"], font("serif_i", 46), sub, w - 150, lh=1.25)
    if s.get("tag"):
        f = font("en_b", 30)
        tw = d.textlength(s["tag"], font=f)
        d.rounded_rectangle((w - 72 - tw - 60, h - 190, w - 72, h - 130), radius=30, fill=GOLD)
        d.text((w - 72 - tw - 30, h - 181), s["tag"], font=f, fill=MAROON)
    brand(d, size, dark, page)
    footer(d, size, dark, credit_of(s["img"], footage) if s.get("img") else "")
    return border(im)


def t_pat(s, size, src, footage, page):
    """Kalighat-pat illustration with the text on its blank paper top."""
    im = cover_crop(load(src, s["img"]), size, 0.5, s.get("cy", 0.55))
    d = ImageDraw.Draw(im)
    w, h = size
    if s.get("num"):
        d.ellipse((66, 140, 146, 220), fill=RED)
        f = font("bn_b", 48)
        tw = d.textlength(s["num"], font=f)
        d.text((106 - tw / 2, 146), s["num"], font=f, fill=CREAM)
        x0 = 170
    else:
        x0 = 70
    f = fit_font(d, s["bn"], "bn_b", 62, w - x0 - 70, 44, max_lines=2)
    fe = font("serif_i", 40)
    th = len(wrap(d, s["bn"], f, w - x0 - 70)) * int(f.size * 1.28) + len(wrap(d, s["en"], fe, w - x0 - 70)) * int(40 * 1.25)
    im = panel(im, (50, 124, w - 50, 160 + th), CREAM, 235)
    im = panel(im, (40, h - 130, w - 40, h - 40), CREAM, 240)
    d = ImageDraw.Draw(im)
    if s.get("num"):
        d.ellipse((66, 140, 146, 220), fill=RED)
        fn = font("bn_b", 48)
        d.text((106 - d.textlength(s["num"], font=fn) / 2, 146), s["num"], font=fn, fill=CREAM)
    y = text_block(d, (x0, 136), s["bn"], f, MAROON, w - x0 - 70, lh=1.28)
    text_block(d, (x0, y + 4), s["en"], fe, INK, w - x0 - 70, lh=1.25)
    brand(d, size, False, page)
    footer(d, size, False, credit_of(s["img"], footage))
    return border(im)


def t_versus(s, size, src, footage, page):
    """Split screen: two photos with labels, the question on top."""
    w, h = size
    im = Image.new("RGB", size, (20, 6, 8))
    half = (w // 2, h)
    for i, (ref, cx) in enumerate(((s["left"], s.get("lcx", 0.5)), (s["right"], s.get("rcx", 0.5)))):
        im.paste(cover_crop(load(src, ref), half, cx, 0.5), (i * w // 2, 0))
    im = Image.alpha_composite(im.convert("RGBA"), gradient(size, top=230, start=0.55, bottom=230)).convert("RGB")
    d = ImageDraw.Draw(im)
    f = fit_font(d, s["bn"], "callig", 104, w - 140, 64, max_lines=2)
    th = len(wrap(d, s["bn"], f, w - 140)) * int(f.size * 1.12) + len(wrap(d, s["en"], font("serif_i", 42), w - 140)) * int(42 * 1.25)
    im = panel(im, (50, 128, w - 50, 160 + th), (30, 6, 8), 205)
    d = ImageDraw.Draw(im)
    d.line((w // 2, 175 + th, w // 2, h), fill=GOLD, width=6)
    vs = font("serif_i", 64)
    d.ellipse((w // 2 - 62, h // 2 - 62, w // 2 + 62, h // 2 + 62), fill=RED, outline=GOLD, width=5)
    d.text((w // 2 - d.textlength("vs", font=vs) / 2, h // 2 - 46), "vs", font=vs, fill=CREAM)
    y = text_block(d, (70, 140), s["bn"], f, CREAM, w - 140, lh=1.12, align="center", shadow=(0, 0, 0))
    text_block(d, (70, y), s["en"], font("serif_i", 42), GOLD, w - 140, align="center")
    lf = font("callig", 76)
    for i, lab in enumerate((s["lbl"], s["rbl"])):
        cx = w // 4 + i * w // 2
        d.text((cx - d.textlength(lab, font=lf) / 2, h - 300), lab, font=lf, fill=CREAM)
    brand(d, size, True, page)
    credits = "; ".join(dict.fromkeys(f"{footage[r]['artist']} ({footage[r]['license']})" for r in (s["left"], s["right"])))
    footer(d, size, True, "Photos: " + credits)
    return border(im)


def t_list(s, size, src, footage, page):
    """Paper slide: a heading and two columns (or one) of items."""
    im = paper(size, seed=len(s["bn"]))
    d = ImageDraw.Draw(im)
    w, h = size
    alpona(d, w - 150, h - 290, 70, (RED[0], RED[1], RED[2]))
    f = fit_font(d, s["bn"], "callig", 110, w - 140, 64, max_lines=2)
    y = text_block(d, (70, 150), s["bn"], f, MAROON, w - 140, lh=1.12)
    y = text_block(d, (72, y + 4), s["en"], font("serif_i", 42), INK, w - 150) + 30
    cols = s["cols"]
    cw = (w - 140 - 40 * (len(cols) - 1)) // len(cols)
    for i, col in enumerate(cols):
        x, yy = 70 + i * (cw + 40), y
        d.text((x, yy), col["head"], font=font("bn_b", 64), fill=RED)
        yy += 96
        for it in col["items"]:
            d.ellipse((x, yy + 20, x + 14, yy + 34), fill=GOLD)
            yy = text_block(d, (x + 30, yy), it, font("bn_m", 46), INK, cw - 30, lh=1.3) + 22
    brand(d, size, False, page)
    footer(d, size, False)
    return border(im)


def t_cta(s, size, src, footage, page):
    im = paper(size, seed=99)
    d = ImageDraw.Draw(im)
    w, h = size
    alpona(d, w // 2, 330 if h == 1350 else 520, 120, RED)
    y = 520 if h == 1350 else 760
    f = fit_font(d, s["bn"], "callig", 104, w - 160, 64, max_lines=3)
    y = text_block(d, (80, y), s["bn"], f, MAROON, w - 160, lh=1.15, align="center")
    y = text_block(d, (90, y + 16), s["en"], font("serif_i", 44), INK, w - 180, align="center", lh=1.3)
    if s.get("tag"):
        f = font("en_b", 32)
        tw = d.textlength(s["tag"], font=f)
        d.rounded_rectangle((w / 2 - tw / 2 - 34, y + 40, w / 2 + tw / 2 + 34, y + 106), radius=33, fill=RED)
        d.text((w / 2 - tw / 2, y + 51), s["tag"], font=f, fill=CREAM)
    brand(d, size, False, page)
    footer(d, size, False)
    return border(im)


def t_prompt(s, size, src, footage, page):
    """A fill-in-the-blank or question post over a photo or pat illustration, text on top."""
    im = cover_crop(load(src, s["img"]), size, s.get("cx", 0.5), s.get("cy", 0.6))
    pat = s["img"].startswith("k")
    if not pat:
        im = Image.alpha_composite(im.convert("RGBA"), gradient(size, top=235, start=0.6, bottom=200)).convert("RGB")
    d = ImageDraw.Draw(im)
    w, h = size
    ink, sub = (MAROON, INK) if pat else (CREAM, GOLD)
    f = fit_font(d, s["bn"], "callig", 128, w - 140, 70, max_lines=3)
    y = text_block(d, (70, 140), s["bn"], f, ink, w - 140, lh=1.1, align="center", shadow=None if pat else (0, 0, 0))
    if s.get("blank"):
        d.line((200, y + 40, w - 200, y + 40), fill=RED if pat else GOLD, width=8)
        y += 80
    text_block(d, (90, y + 10), s["en"], font("serif_i", 44), sub, w - 180, align="center", lh=1.25)
    brand(d, size, not pat, page)
    footer(d, size, not pat, credit_of(s["img"], footage))
    return border(im)


def t_bingo(s, size, src, footage, page):
    im = paper(size, seed=4)
    d = ImageDraw.Draw(im)
    w, h = size
    f = font("callig", 104)
    d.text(((w - d.textlength(s["bn"], font=f)) / 2, 128), s["bn"], font=f, fill=MAROON)
    text_block(d, (90, 262), s["en"], font("serif_i", 36), INK, w - 180, align="center")
    n, gx, gy, gap = 4, 70, 350, 12
    cw = (w - 2 * gx - gap * (n - 1)) // n
    ch = (h - gy - 150 - gap * (n - 1)) // n
    for i, (bn, en) in enumerate(s["cells"]):
        x, y = gx + (i % n) * (cw + gap), gy + (i // n) * (ch + gap)
        fill = (RED if (i % 2) ^ ((i // n) % 2) else (247, 228, 196))
        d.rounded_rectangle((x, y, x + cw, y + ch), radius=14, fill=fill, outline=GOLD, width=3)
        ink = CREAM if fill == RED else MAROON
        fb = fit_font(d, bn, "bn_b", 36, cw - 24, 26, max_lines=2)
        lines = wrap(d, bn, fb, cw - 24)
        ty = y + ch / 2 - (len(lines) * fb.size * 1.2 + 34) / 2
        ty = text_block(d, (x + 12, ty), bn, fb, ink, cw - 24, lh=1.2, align="center", max_lines=2)
        text_block(d, (x + 12, ty + 2), en, font("en", 22), ink, cw - 24, lh=1.15, align="center", max_lines=2)
    brand(d, size, False, page)
    footer(d, size, False)
    return border(im)


def t_story(s, size, src, footage, page):
    """1080×1920 story: photo or pat art, question on top, an empty band in the middle for Instagram's sticker."""
    im = cover_crop(load(src, s["img"]), size, s.get("cx", 0.5), s.get("cy", 0.5))
    pat = s["img"].startswith("k")
    im = Image.alpha_composite(im.convert("RGBA"), gradient(size, top=0 if pat else 230, start=0.62, bottom=210)).convert("RGB")
    d = ImageDraw.Draw(im)
    w, h = size
    ink, sub = (MAROON, INK) if pat else (CREAM, GOLD)
    if pat:  # a paper panel keeps the text readable over the drawing
        d.rounded_rectangle((60, 150, w - 60, 560), radius=28, fill=(255, 244, 224))
    f = fit_font(d, s["bn"], "callig", 120, w - 160, 70, max_lines=2)
    y = text_block(d, (80, 190), s["bn"], f, ink, w - 160, lh=1.1, align="center", shadow=None if pat else (0, 0, 0))
    text_block(d, (90, y + 10), s["en"], font("serif_i", 46), sub, w - 180, align="center")
    if s.get("hint"):
        hf = font("en_b", 28)
        d.text(((w - d.textlength(s["hint"], font=hf)) / 2, h - 300), s["hint"], font=hf, fill=CREAM)
    brand(d, size, not pat, None)
    footer(d, size, True, credit_of(s["img"], footage))
    return border(im)


T = {"word": t_word, "cover": t_cover, "pat": t_pat, "versus": t_versus, "list": t_list, "cta": t_cta,
     "prompt": t_prompt, "bingo": t_bingo, "story": t_story}


def credits(post, footage):
    refs = []
    for s in post["slides"]:
        for k in ("img", "left", "right"):
            if s.get(k) and s[k] not in refs:
                refs.append(s[k])
        refs += [r for r in s.get("grid", []) if r not in refs]
    photos = dict.fromkeys(f"{footage[r]['artist']} ({footage[r]['license']})" for r in refs if r.startswith("p"))
    parts = []
    if photos:
        parts.append("📷 Photos (Wikimedia Commons): " + "; ".join(photos))
    if any(r.startswith("k") for r in refs):
        parts.append("🎨 Illustrations made with AI in the Kalighat pat style.")
    return " ".join(parts)


def main():
    spec_p, footage_p, src, out = sys.argv[1:5]
    only = set(sys.argv[5].split(",")) if len(sys.argv) > 5 else None
    spec = json.load(open(spec_p, encoding="utf-8"))
    footage = json.load(open(footage_p, encoding="utf-8"))
    os.makedirs(out, exist_ok=True)
    for post in spec["posts"]:
        if only and post["id"] not in only:
            continue
        size = SIZES[post.get("size", "post")]
        n = len(post["slides"])
        d = os.path.join(out, post["id"])
        os.makedirs(d, exist_ok=True)
        for i, s in enumerate(post["slides"], 1):
            im = T[s["t"]](s, size, src, footage, (i, n) if n > 1 and post.get("size", "post") == "post" else None)
            im.save(os.path.join(d, f"slide-{i:02d}.jpg"), quality=92, optimize=True)
        c = post.get("caption")
        if c:
            cr = credits(post, footage)
            with open(os.path.join(d, "caption.txt"), "w", encoding="utf-8") as f:
                f.write(f"{c['bn']}\n\n{c['en']}\n\n{c['tags']}" + (f"\n\n{cr}" if cr else "") + "\n")
        print("rendered", post["id"], n, flush=True)


if __name__ == "__main__":
    main()
