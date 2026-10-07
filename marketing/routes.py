"""Area-wise pandal route carousel: "Don't pandal hop randomly", one slide per zone with the real walking route.

    python -m marketing.routes --out out/routes [--zones north,central,...]

Each zone slide draws the guide's own walking order (app/data/guide.json: zones[].route) on its true geography, with
numbered stops, the metro station to start from, distance and steps, over a darkened strip collage of that zone's
pandal photos (Wikimedia Commons, credited in the caption). Cover, a city overview and a "Comment PUJO" close.
Writes slide-NN.jpg (1440x1800) and credits.json. Needs Pillow (with raqm for Bengali) and network for the photos.
"""
import argparse
import hashlib
import json
import math
import os
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
W, H = 1440, 1800
YEL, WHITE, INK = (255, 205, 41), (255, 255, 255), (20, 12, 8)
UA = {"User-Agent": "PujoParikramaBot/1.0 (https://pujoparikramaguide.in)"}
ZONES = ["north", "central", "south_lakemarket", "south_gariahat", "bhowanipore", "kasba", "salt_lake",
         "lake_town_dumdum", "southwest"]
BEST = {"north": "Heritage, bonedi bari, Kumartuli", "central": "Theme blockbusters, big crowds",
        "south_lakemarket": "Heavyweight pujas close together", "south_gariahat": "Ekdalia, Singhi Park, shopping",
        "bhowanipore": "Classic neighbourhood pujas", "kasba": "Bold theme pandals",
        "salt_lake": "Block pujas, open space", "lake_town_dumdum": "Sreebhumi and the north-east giants",
        "southwest": "Behala's art-trail pujas", "jadavpur_santoshpur": "Quieter south-east pujas",
        "tolly_naktala": "Naktala and Tollygunge", "beleghata": "East Kolkata stop", "howrah": "Across the river"}
FONT_DIRS = [os.environ.get("FONTS", "fonts"), str(ROOT / "marketing" / "reels" / "fonts"), "/usr/share/fonts/truetype/dejavu"]


def font(name, size, bengali=False):
    for d in FONT_DIRS:
        p = Path(d) / name
        if p.exists():
            return ImageFont.truetype(str(p), size, layout_engine=ImageFont.Layout.RAQM if bengali else None)
    fb = "DejaVuSans-Bold.ttf" if not bengali else "DejaVuSans.ttf"
    return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{fb}", size)


def F(kind, size):
    return {"display": lambda: font("Anton-Regular.ttf", size), "bold": lambda: font("Poppins-Bold.ttf", size),
            "semi": lambda: font("Poppins-SemiBold.ttf", size), "med": lambda: font("Poppins-Medium.ttf", size),
            "bn": lambda: font("Galada-Regular.ttf", size, True), "bnb": lambda: font("HindSiliguri-Bold.ttf", size, True)}[kind]()


def fetch(url, cache):
    p = Path(cache) / ("r-" + hashlib.sha1(url.encode()).hexdigest()[:12] + ".jpg")
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
            p.write_bytes(r.read())
    return p


def big(src):
    """Commons thumbnail URL at 1280 px (a size Wikimedia serves), else as is."""
    s = src.split("?")[0]
    return s.replace("/960px-", "/1280px-") if "/thumb/" in s else s


def cover_fit(im, w, h, cy=0.45):
    im = ImageOps.exif_transpose(im).convert("RGB")
    k = max(w / im.width, h / im.height)
    im = im.resize((max(w, round(im.width * k)), max(h, round(im.height * k))), Image.LANCZOS)
    x = (im.width - w) // 2
    y = min(max(0, round(im.height * cy - h / 2)), im.height - h)
    return im.crop((x, y, x + w, y + h))


def collage(paths, dark=0.58):
    """Horizontal strips of photos, darkened, like a contact sheet of the zone."""
    n = max(1, len(paths))
    base = Image.new("RGB", (W, H), INK)
    hs = [H // n + (1 if i < H % n else 0) for i in range(n)]
    y = 0
    for p, h in zip(paths, hs):
        try:
            base.paste(cover_fit(Image.open(p), W, h), (0, y))
        except Exception:
            pass
        y += h
    shade = Image.new("RGB", (W, H), (0, 0, 0))
    out = Image.blend(base, shade, dark)
    grad = Image.linear_gradient("L").resize((W, H))  # darker towards the bottom for the text panel
    return Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), out, grad.point(lambda v: int(v * 0.45)))


def text(d, xy, s, f, fill=WHITE, anchor="la", stroke=0):
    d.text(xy, s, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=(0, 0, 0))


def fit(d, s, kind, size, maxw, minsize=24):
    """Largest font of this kind (from size down) that fits s in maxw."""
    while size > minsize and d.textlength(s, font=F(kind, size)) > maxw:
        size -= 2
    return F(kind, size)


def spread(xy, box, gap=74, fixed=0, iters=300):
    """Pushes stops that sit on top of each other apart (keeping the route's shape) so every number reads."""
    pts = [list(p) for p in xy]
    x0, y0, x1, y1 = box
    for _ in range(iters):
        moved = False
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                dx, dy = pts[j][0] - pts[i][0], pts[j][1] - pts[i][1]
                dist = math.hypot(dx, dy)
                if dist < gap:
                    if dist < 1e-6:
                        dx, dy, dist = 1.0, 0.7, 1.22
                    push = (gap - dist) / 2 + 0.5
                    ux, uy = dx / dist, dy / dist
                    for k, sgn in ((i, -1), (j, 1)):
                        if k >= fixed:
                            pts[k][0] = min(max(x0, pts[k][0] + sgn * ux * push), x1)
                            pts[k][1] = min(max(y0, pts[k][1] + sgn * uy * push), y1)
                    moved = True
        if not moved:
            break
    return [tuple(p) for p in pts]


def wrap(d, s, f, width):
    out, line = [], ""
    for w in s.split():
        t = (line + " " + w).strip()
        if d.textlength(t, font=f) <= width:
            line = t
        else:
            out.append(line)
            line = w
    return out + [line] if line else out


def header(d, title, sub_bn, kicker, size=128):
    text(d, (90, 110), kicker.upper(), F("semi", 34), fill=YEL)
    y = 160
    lines = wrap(d, title.upper(), F("display", size), W - 180)
    while size > 70 and (len(lines) > 2 or max(d.textlength(l, font=F("display", size)) for l in lines) > W - 180):
        size -= 8
        lines = wrap(d, title.upper(), F("display", size), W - 180)
    for ln in lines:
        text(d, (90, y), ln, F("display", size), fill=YEL, stroke=2)
        y += int(size * 1.03)
    text(d, (92, y + 6), sub_bn, fit(d, sub_bn, "bn", 54, W - 180), stroke=2)
    return y + 80


def project(pts, box):
    """lat/lng → pixels in box (x0, y0, x1, y1), equal scale on both axes (true shape), north up."""
    lat0 = sum(p[0] for p in pts) / len(pts)
    xs = [p[1] * math.cos(math.radians(lat0)) for p in pts]
    ys = [-p[0] for p in pts]
    x0, y0, x1, y1 = box
    sx = (x1 - x0) / max(1e-9, max(xs) - min(xs))
    sy = (y1 - y0) / max(1e-9, max(ys) - min(ys))
    s = min(sx, sy)
    ox = x0 + ((x1 - x0) - s * (max(xs) - min(xs))) / 2
    oy = y0 + ((y1 - y0) - s * (max(ys) - min(ys))) / 2
    return [(ox + (x - min(xs)) * s, oy + (y - min(ys)) * s) for x, y in zip(xs, ys)]


def dotted(d, a, b, gap=22, r=5):
    dist = math.dist(a, b)
    for i in range(int(dist // gap) + 1):
        t = i * gap / dist if dist else 0
        x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        d.ellipse((x - r, y - r, x + r, y + r), fill=WHITE)


def overlap(a, b):
    """Area shared by two (x0, y0, x1, y1) boxes."""
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def place_label(anchor, size, obstacles, bounds, gap=48):
    """The box for a label of size (w, h) next to anchor (x, y): right, left, above or below, whichever hits the
    fewest obstacles (and never leaves bounds)."""
    (x, y), (w, h) = anchor, size
    bx0, by0, bx1, by1 = bounds
    best = None
    for cx, cy in ((x + gap, y - h / 2), (x - gap - w, y - h / 2), (x - w / 2, y - gap - h), (x - w / 2, y + gap),
                   (x + gap, y - gap - h), (x + gap, y + gap), (x - gap - w, y - gap - h), (x - gap - w, y + gap)):
        cx, cy = min(max(bx0, cx), bx1 - w), min(max(by0, cy), by1 - h)
        r = (cx, cy, cx + w, cy + h)
        cost = sum(overlap(r, o) for o in obstacles) + 4 * overlap(r, (x - 40, y - 40, x + 40, y + 40))
        if best is None or cost < best[0]:
            best = (cost, r)
    return best[1]


def clear_of(xy, rect, box, pad=36, fixed=1):
    """Moves stops whose circle touches rect to just above or below it (whichever is nearer), inside box."""
    out = []
    for k, (x, y) in enumerate(xy):
        if k >= fixed and rect[0] - pad < x < rect[2] + pad and rect[1] - pad < y < rect[3] + pad:
            up, down = rect[1] - pad, rect[3] + pad
            y = up if (y - up < down - y and up >= box[1]) or down > box[3] else down
        out.append((x, y))
    return out


def zone_slide(z, g, cache):
    P = {p["id"]: p for p in g["pandals"]}
    T = {t["id"]: t for t in g["transit"]}
    order = [P[i] for i in z["route"]["order"] if i in P]
    photos, credits = [], []
    for p in order:
        for ph in p.get("photos") or []:
            if len(photos) < 3:
                try:
                    photos.append(fetch(big(ph["src"]), cache))
                    credits.append(f"{ph.get('author', 'Unknown')} ({ph.get('license', '')})")
                except Exception:
                    pass
                break
    im = collage(photos)
    d = ImageDraw.Draw(im, "RGBA")
    st = T.get(z["route"].get("start")) or T.get(z.get("entry_station"))
    title = z["name"] if len(z["name"]) <= 22 else z.get("short", z["name"])
    y = header(d, title, z.get("short_bn") if title != z["name"] else z.get("name_bn", ""), f"{len(order)} pandals · walking route")
    # map: the stops in walking order on their real geography, start station first
    pts = ([(st["lat"], st["lng"])] if st else []) + [(p["lat"], p["lng"]) for p in order]
    row = 64 if len(order) > 14 else 70 if len(order) > 10 else 84
    list_h = row * math.ceil(len(order) / 2) + 30
    box = (170, y + 50, W - 170, H - 330 - list_h)
    gap = 80 if len(order) <= 12 else 70
    xy = spread(project(pts, box), box, gap=gap)
    lab_box = None
    if st:  # the start label goes where it covers the fewest stops, then any stop still under it moves off
        lab = f"Start: {st['name'].replace(' Sutanuti', '')} Metro"
        fl = F("semi", 34)
        size = (d.textlength(lab, font=fl) + 28, 56)
        for _ in range(3):
            stops = [(x - 34, y - 34, x + 34, y + 34) for x, y in xy[1:]]
            lab_box = place_label(xy[0], size, stops, (40, box[1] - 40, W - 40, box[3] + 40))
            if not any(overlap(lab_box, o) for o in stops):
                break
            xy = spread(clear_of(xy, lab_box, (box[0], box[1] - 40, box[2], box[3] + 40)), box, gap=gap, fixed=1)
    for a, b in zip(xy, xy[1:]):
        dotted(d, a, b)
    if st:
        x, yy = xy[0]
        d.rounded_rectangle((x - 34, yy - 34, x + 34, yy + 34), 14, fill=(30, 110, 230, 255), outline=WHITE, width=4)
        text(d, (x, yy + 2), "M", F("bold", 40), anchor="mm")
        d.rounded_rectangle(lab_box, 14, fill=(10, 30, 70, 235))
        text(d, (lab_box[0] + 14, (lab_box[1] + lab_box[3]) / 2), lab, fl, anchor="lm")
        xy = xy[1:]
    for n, (x, yy) in enumerate(xy, 1):
        d.ellipse((x - 30, yy - 30, x + 30, yy + 30), fill=YEL, outline=INK, width=3)
        text(d, (x, yy + 1), str(n), F("bold", 32), fill=INK, anchor="mm")
    # numbered list in two columns
    ly = H - 300 - list_h + 20
    half = math.ceil(len(order) / 2)
    for i, p in enumerate(order):
        col, rr = divmod(i, half)
        x = 90 + col * (W - 180) // 2
        yy = ly + rr * row
        d.ellipse((x, yy, x + 52, yy + 52), fill=YEL)
        text(d, (x + 26, yy + 27), str(i + 1), F("bold", 28), fill=INK, anchor="mm")
        name = p["name"]
        f = F("semi", 36)
        while d.textlength(name, font=f) > (W - 180) // 2 - 80 and len(name) > 8:
            name = name[:-2].rstrip() + "…" if not name.endswith("…") else name[:-3].rstrip() + "…"
        text(d, (x + 68, yy + 26), name, f, anchor="lm", stroke=2)
    # facts panel
    r = z["route"]
    d.rounded_rectangle((70, H - 270, W - 70, H - 70), 34, fill=(0, 0, 0, 170))
    facts = f"{len(order)} pandals  ·  {r['walk_m'] / 1000:.1f} km  ·  ~{round(r['steps'], -2):,} steps  ·  ~{round(r['walk_min'] / 60, 1):g} h walking"
    text(d, (110, H - 222), facts, fit(d, facts, "bold", 40, W - 220), fill=YEL)
    best = BEST.get(z["id"], z.get("vibe", ""))
    text(d, (110, H - 160), f"Best for: {best}", F("med", 36))
    text(d, (110, H - 108), "Quiet hours and live crowd for every stop: link in bio", F("med", 30), fill=(230, 230, 230))
    return im, credits


def cover(g, cache, hero_url):
    im = cover_fit(Image.open(fetch(hero_url, cache)), W, H, 0.4)
    im = Image.blend(im, Image.new("RGB", (W, H), (0, 0, 0)), 0.35)
    d = ImageDraw.Draw(im, "RGBA")
    y = 980
    for ln in ["DON'T PANDAL HOP", "RANDOMLY THIS", "DURGA PUJA"]:
        text(d, (W // 2, y), ln, fit(d, ln, "display", 150, W - 120), fill=YEL, anchor="mm", stroke=4)
        y += 160
    text(d, (W // 2, y + 20), "এলোমেলো ঘুরে রাত নষ্ট নয়!", F("bn", 70), anchor="mm", stroke=3)
    d.rounded_rectangle((W // 2 - 420, y + 95, W // 2 + 420, y + 185), 45, fill=YEL)
    text(d, (W // 2, y + 140), "Save these area-wise routes", F("bold", 44), fill=INK, anchor="mm")
    text(d, (W // 2, 90), "@pujoparikrama.guide", F("semi", 38), anchor="mm", stroke=2)
    return im


def overview(g, zones):
    im = Image.new("RGB", (W, H), (16, 10, 8))
    d = ImageDraw.Draw(im, "RGBA")
    y = header(d, "How to use this guide", "এক রাতে এক-দুটো এলাকা", "pujo 2026 · 17-21 Oct")
    Z = {z["id"]: z for z in g["zones"]}
    pts = [(Z[i]["lat"], Z[i]["lng"]) for i in zones]
    blue = [t for t in g["transit"] if t.get("line") == "blue"]
    allp = pts + [(t["lat"], t["lng"]) for t in blue if 22.45 < t["lat"] < 22.66]
    box = (160, y + 40, W - 160, H - 360)
    xy = project(allp, box)
    xy = spread(xy[:len(pts)], box, gap=80) + xy[len(pts):]
    bl = xy[len(pts):]
    for a, b in zip(bl, bl[1:]):
        d.line((a, b), fill=(60, 130, 255, 230), width=10)
    taken = [(x - 30, yy - 30, x + 30, yy + 30) for x, yy in xy[:len(pts)]]
    fl = F("semi", 38)
    for i, (x, yy) in zip(zones, xy[:len(pts)]):
        d.ellipse((x - 26, yy - 26, x + 26, yy + 26), fill=YEL, outline=INK, width=3)
        r = place_label((x, yy), (d.textlength(Z[i]["short"], font=fl), 46), taken, (40, box[1] - 30, W - 40, box[3] + 30), gap=36)
        taken.append(r)
        text(d, (r[0], (r[1] + r[3]) / 2), Z[i]["short"], fl, anchor="lm", stroke=3)
    d.rounded_rectangle((70, H - 300, W - 70, H - 70), 34, fill=(0, 0, 0, 170))
    for k, s in enumerate(["Pick one zone a night. Start at its metro station.",
                           "Follow the numbers: the route is the real walking order.",
                           "Blue line = Metro. Each slide has distance and steps."]):
        text(d, (110, H - 250 + k * 62), s, F("med", 38))
    return im


def closing(hero_path):
    im = cover_fit(Image.open(hero_path), W, H, 0.35)
    im = Image.blend(im, Image.new("RGB", (W, H), (0, 0, 0)), 0.55)
    d = ImageDraw.Draw(im, "RGBA")
    text(d, (W // 2, 700), "COMMENT", F("display", 170), fill=WHITE, anchor="mm", stroke=4)
    text(d, (W // 2, 880), "“PUJO”", F("display", 260), fill=YEL, anchor="mm", stroke=5)
    for k, s in enumerate(["and we'll DM you every route,", "the metro stops and the quiet hours"]):
        text(d, (W // 2, 1080 + k * 70), s, F("semi", 52), anchor="mm", stroke=3)
    text(d, (W // 2, 1290), "কমেন্টে লিখুন “পুজো”, রুট পাঠিয়ে দেব!", F("bn", 64), anchor="mm", stroke=3)
    d.rounded_rectangle((W // 2 - 430, 1440, W // 2 + 430, 1540), 50, fill=YEL)
    text(d, (W // 2, 1490), "Save it · send it to your pujo gang", F("bold", 44), fill=INK, anchor="mm")
    return im


def build(out, zones=None, cache=None):
    g = json.loads((ROOT / "app" / "data" / "guide.json").read_text(encoding="utf-8"))
    zones = zones or ZONES
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    cache = cache or str(out / "_src")
    hero = "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f5/Maa_Durga_Face.jpg/1280px-Maa_Durga_Face.jpg"
    slides, credits = [cover(g, cache, hero)], ["Chinsurah Sarbojonin Durgotsab Samity (CC0)"]
    slides.append(overview(g, zones))
    Z = {z["id"]: z for z in g["zones"]}
    for zid in zones:
        im, cr = zone_slide(Z[zid], g, cache)
        slides.append(im)
        for c in cr:
            if c not in credits:
                credits.append(c)
    slides.append(closing(fetch(hero, cache)))
    for n, im in enumerate(slides, 1):
        im.save(out / f"slide-{n:02d}.jpg", quality=92, optimize=True, progressive=True)
    (out / "credits.json").write_text(json.dumps(credits, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(slides), credits


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--zones")
    a = ap.parse_args(argv)
    n, cr = build(a.out, a.zones.split(",") if a.zones else None)
    print(f"{n} slides → {a.out}; photos by {len(cr)} photographers")


if __name__ == "__main__":
    main()
