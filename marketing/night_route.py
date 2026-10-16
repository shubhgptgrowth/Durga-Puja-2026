"""Night-map route reel: the same walking route as marketing/route_reel.py, drawn as a glowing red line on a dark street
map, with the area's best-known pandals lit up as photo medallions and a walker who sets off from the Metro.

    python -m marketing.night_route --zone north --area "North Kolkata" --out out/n.mp4
    python -m marketing.night_route --zone north --area "North Kolkata" --part 1 --next "Central Kolkata" --out out/n.mp4
    python -m marketing.night_route --zone north --still 0 --out cover.jpg      # one frame (0 = the cover)

Frame 1 is the cover: "১৭টা পুজো · ১ রাতে" (the count from the guide), "<Area> Master Route", the whole route glowing
from the Metro start, the medallions and the walker. The route then dims and redraws stop by stop behind the walker
while a card names each pandal and the distance so far, holds on the full walk (steps, hours), and ends on "Save
this route" and "Comment PUJO". Every number comes from app/data/guide.json; the medallion photos are the pandals' own
Wikimedia Commons photos (credited on the end frame with the map and the dhak). 1080x1920, 30 fps, text inside
Instagram's safe area. Needs Pillow (with raqm), ffmpeg, pmtiles and mapbox-vector-tile.
"""
import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .route_reel import AUDIO, AUDIO_CREDIT, HANDLE, LINE_RGB, ease, route, short_name
from .routes import F, ROOT, fetch, fit, overlap, spread

W, H, FPS = 1080, 1920, 30
BG = (9, 11, 20)
WHITE, CREAM, MUTE = (255, 255, 255), (246, 232, 214), (172, 160, 160)
RED, RED_HI, GOLD = (255, 62, 62), (255, 190, 176), (255, 196, 92)
FIT = (120, 700, 880, 1240)  # where the route is fitted: under the header, clear of the right rail and the card
PAD = 30  # glow around a medallion frame
CACHE = Path.home() / ".cache" / "pujo-night-route"
BN_NUM = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def station_name(st):
    """'Sovabazar Metro', or 'Ballygunge Junction station' for a suburban rail start."""
    n = st["name"].replace(" Sutanuti", "").replace(" (Suburban)", "")
    return f"{n} Metro" if st.get("line") in LINE_RGB else f"{n} station"


def photo_of(p):
    """The pandal's first JPEG/PNG Commons photo: (url, author, licence), or None."""
    for ph in p.get("photos") or []:
        if ph.get("page", "").rsplit(".", 1)[-1].lower() in ("jpg", "jpeg", "png"):
            return ph["src"].split("?")[0], ph.get("author") or "", ph.get("license") or ""
    return None


def plan(zone_id=None, g=None, ids=None, title=None, title_bn=None, area=None, part=None, nxt=None, ordered=False, max_lit=5):
    g = g or json.loads((ROOT / "app" / "data" / "guide.json").read_text(encoding="utf-8"))
    rt = route(g, zone_id, ids, title, title_bn, ordered)
    order, st = rt["order"], rt["station"]
    geo = ([(st["lat"], st["lng"])] if st else []) + [(p["lat"], p["lng"]) for p in order]
    lat0 = sum(q[0] for q in geo) / len(geo)
    c0 = math.cos(math.radians(lat0))
    xs, ys = [q[1] * c0 for q in geo], [-q[0] for q in geo]
    s = min((FIT[2] - FIT[0]) / max(0.004, max(xs) - min(xs)), (FIT[3] - FIT[1]) / max(0.004, max(ys) - min(ys)))
    ox = FIT[0] + ((FIT[2] - FIT[0]) - s * (max(xs) - min(xs))) / 2
    oy = FIT[1] + ((FIT[3] - FIT[1]) - s * (max(ys) - min(ys))) / 2
    to_px = lambda la, lo: (ox + (lo * c0 - min(xs)) * s, oy + (-la - min(ys)) * s)
    from_px = lambda x, y: (-((y - oy) / s + min(ys)), ((x - ox) / s + min(xs)) / c0)
    xy = spread([to_px(*q) for q in geo], FIT, gap=34, fixed=1 if st else 0)
    off = 1 if st else 0
    # the lit medallions: the best-known stops with a photo, kept apart so none covers another
    cands = sorted((i for i, p in enumerate(order) if photo_of(p)), key=lambda i: (-(order[i].get("tier") or 0), i))
    lit = []
    for i in cands:
        x, y = xy[off + i]
        if all(math.dist((x, y), xy[off + j]) > 230 for j in lit) and len(lit) < max_lit:
            lit.append(i)
    legs = [math.dist(a, b) for a, b in zip(xy, xy[1:])]
    km, tot = [0.0], sum(legs) or 1
    for leg in legs:
        km.append(km[-1] + leg / tot * rt["walk_m"] / 1000)
    per = min(0.9, max(0.5, 10.0 / max(1, len(order))))
    t_draw = 2.4
    return {**rt, "xy": xy, "off": off, "lit": sorted(lit), "km": km, "to_px": to_px, "from_px": from_px,
            "area": area or rt["area"], "part": part, "next": nxt, "per": per, "t_dim": 1.8, "t_draw": t_draw,
            "t_hold": t_draw + per * len(order), "t_end": t_draw + per * len(order) + 2.6}


def glow(size, draw_fn, blur=14, scale=4):
    """A soft glow layer: draw_fn(ImageDraw, k) draws at 1/scale size (k = 1/scale), blurred and scaled back up."""
    small = Image.new("RGBA", (size[0] // scale, size[1] // scale), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(small, "RGBA"), 1 / scale)
    return small.filter(ImageFilter.GaussianBlur(blur / scale)).resize(size, Image.BILINEAR)


def neon(im, path, a=1.0, width=7):
    """The route as a red neon tube: a wide blurred halo, the tube, a pale core."""
    if len(path) < 2:
        return
    halo = glow(im.size, lambda d, k: d.line([(x * k, y * k) for x, y in path], fill=RED + (int(200 * a),), width=max(2, int(34 * k)), joint="curve"), blur=18)  # noqa: E501
    comp(im, halo)
    d = ImageDraw.Draw(im, "RGBA")
    d.line(path, fill=RED + (int(255 * a),), width=width, joint="curve")
    d.line(path, fill=RED_HI + (int(230 * a),), width=2, joint="curve")


def dot(d, q, r=9, a=255, ring=RED):
    x, y = q
    d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 250, 244, a), outline=ring + (a,), width=4)


_HALO = {}


def halo(a):
    """The lamp's glow as a small sprite (120x120, centred on the lamp), one per brightness."""
    k = round(a, 1)
    if k not in _HALO:
        sp = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
        ImageDraw.Draw(sp).ellipse((30, 22, 90, 76), fill=GOLD + (int(150 * k),))
        _HALO[k] = sp.filter(ImageFilter.GaussianBlur(14))
    return _HALO[k]


def comp(im, layer, pos=(0, 0)):
    """Blend an RGBA layer onto the RGB frame."""
    im.paste(layer, (int(pos[0]), int(pos[1])), layer)


def lamp(im, q, n=None, a=1.0):
    """A small lit pandal for the stops without a medallion: gold, glowing, red roof."""
    x, y = q
    comp(im, halo(a), (x - 60, y - 70))
    d = ImageDraw.Draw(im, "RGBA")
    A = int(255 * a)
    d.polygon([(x - 17, y - 14), (x, y - 33), (x + 17, y - 14)], fill=(214, 40, 40, A))
    d.rectangle((x - 12, y - 14, x + 12, y + 2), fill=GOLD + (A,))
    d.rounded_rectangle((x - 4, y - 9, x + 4, y + 2), 3, fill=(60, 20, 10, A))
    if n is not None:
        d.ellipse((x + 6, y - 46, x + 34, y - 18), fill=(20, 12, 10, A), outline=WHITE + (A,), width=2)
        d.text((x + 20, y - 32), str(n), font=F("bold", 17 if n < 10 else 15), fill=WHITE + (A,), anchor="mm")


def medallion(p, w=128, h=150):
    """The pandal's photo in an arched gold frame with a soft glow: an RGBA image (PAD of glow around the frame)."""
    ph = photo_of(p)
    for attempt in range(4):  # Commons answers 429 to bursts; wait and retry rather than drop the photo
        try:
            src = Image.open(fetch(ph[0], CACHE))
            break
        except OSError:
            if attempt == 3:
                raise
            time.sleep(6 * (attempt + 1))
    src = ImageOps.exif_transpose(src).convert("RGB")
    k = max(w / src.width, h / src.height)
    src = src.resize((max(w, round(src.width * k)), max(h, round(src.height * k))), Image.LANCZOS)
    left, top = (src.width - w) // 2, int((src.height - h) * 0.42)
    src = src.crop((left, top, left + w, top + h))
    arch = lambda dd, x0, y0, ww, hh, fill: (dd.rectangle((x0, y0 + ww // 2, x0 + ww, y0 + hh), fill=fill), dd.ellipse((x0, y0, x0 + ww, y0 + ww), fill=fill))
    mask = Image.new("L", (w, h), 0)
    arch(ImageDraw.Draw(mask), 0, 0, w, h, 255)
    out = Image.new("RGBA", (w + 2 * PAD, h + 2 * PAD), (0, 0, 0, 0))
    halo = Image.new("RGBA", out.size, (0, 0, 0, 0))
    arch(ImageDraw.Draw(halo), PAD - 8, PAD - 8, w + 16, h + 16, GOLD + (190,))
    out.alpha_composite(halo.filter(ImageFilter.GaussianBlur(15)))
    arch(ImageDraw.Draw(out), PAD - 5, PAD - 5, w + 10, h + 10, GOLD + (255,))
    out.paste(src, (PAD, PAD), mask)
    return out


def place(q, size, route_pts, taken, box=(40, 640, 940, 1306)):
    """Where a medallion of size (w, h) goes near stop q: above, below or beside it, off the route and clear of the
    other medallions and labels. Returns the frame's (x0, y0, x1, y1)."""
    (x, y), (w, h) = q, size
    best = None
    for gap in (34, 70, 110):
        for cx, cy in ((x - w / 2, y - gap - h), (x - w / 2, y + gap), (x + gap, y - h / 2), (x - gap - w, y - h / 2),
                       (x + gap * 0.7, y - gap * 0.7 - h), (x - gap * 0.7 - w, y - gap * 0.7 - h),
                       (x + gap * 0.7, y + gap * 0.7), (x - gap * 0.7 - w, y + gap * 0.7)):
            r = (cx, cy, cx + w, cy + h + 40)  # the name sits under the frame
            out = max(0, box[0] - r[0]) + max(0, r[2] - box[2]) + max(0, box[1] - r[1]) + max(0, r[3] - box[3])
            cost = out * 2000 + gap * 4
            cost += 90 * sum(1 for px, py in route_pts if r[0] - 8 < px < r[2] + 8 and r[1] - 8 < py < r[3] + 8)
            cost += sum(overlap(r, o) for o in taken) * 25
            if best is None or cost < best[1]:
                best = (r, cost)
    return best[0]


def walker(d, q, phase=0.0, s=1.0):
    """A small walking figure, white with a red backpack, feet at q."""
    x, y = q
    sw = math.sin(phase) * 0.55
    hip, sh = (x, y - 30 * s), (x + 2 * s, y - 56 * s)
    leg = lambda ang: (hip[0] + math.sin(ang) * 30 * s, hip[1] + math.cos(ang) * 30 * s)
    arm = lambda ang: (sh[0] + math.sin(ang) * 22 * s, sh[1] + math.cos(ang) * 22 * s)
    for p_ in (leg(sw), leg(-sw)):
        d.line([hip, p_], fill=WHITE, width=int(8 * s))
    d.rounded_rectangle((sh[0] - 17 * s, sh[1] - 4 * s, sh[0] - 4 * s, sh[1] + 20 * s), int(4 * s), fill=(214, 40, 40))
    d.line([hip, sh], fill=WHITE, width=int(11 * s))
    for p_ in (arm(-sw), arm(sw)):
        d.line([sh, p_], fill=WHITE, width=int(6 * s))
    d.ellipse((sh[0] - 9 * s, sh[1] - 26 * s, sh[0] + 9 * s, sh[1] - 8 * s), fill=WHITE)


def header(im, pl):
    d = ImageDraw.Draw(im, "RGBA")
    n = len(pl["order"])
    brand = "PUJO PARIKRAMA GUIDE"
    f = F("semi", 26)
    bw = d.textlength(brand, font=f)
    d.text((W // 2, 226), brand, font=f, fill=GOLD, anchor="mm")
    d.line((W // 2 - bw / 2 - 90, 226, W // 2 - bw / 2 - 20, 226), fill=GOLD + (150,), width=2)
    d.line((W // 2 + bw / 2 + 20, 226, W // 2 + bw / 2 + 90, 226), fill=GOLD + (150,), width=2)
    when = "সন্ধ্যায়" if "evening" in (pl.get("hook") or "").lower() else "রাতে"
    num, rest, one = f"{n}".translate(BN_NUM), "টা পুজো · ", "১"
    tail = f" {when}"
    fb = F("bnb", 118)
    parts = [(num, RED), (rest, WHITE), (one, RED), (tail, WHITE)]
    tw = sum(d.textlength(s, font=fb) for s, _ in parts)
    while tw > 920:
        fb = F("bnb", fb.size - 4)
        tw = sum(d.textlength(s, font=fb) for s, _ in parts)
    x = (W - tw) / 2
    for s, c in parts:
        d.text((x, 330), s, font=fb, fill=c, anchor="lm")
        x += d.textlength(s, font=fb)
    a, b = f"{pl['area']} ", "Master Route"
    fe = F("bold", 62)
    while d.textlength(a + b, font=fe) > 900:
        fe = F("bold", fe.size - 2)
    x = (W - d.textlength(a + b, font=fe)) / 2
    d.text((x, 444), a, font=fe, fill=WHITE, anchor="lm")
    d.text((x + d.textlength(a, font=fe), 444), b, font=fe, fill=RED, anchor="lm")
    st = pl["station"]
    sub = f"{pl['walk_m'] / 1000:.1f} km on foot  ·  start at {station_name(st)}" if st else f"{pl['walk_m'] / 1000:.1f} km on foot"
    fs = fit(d, sub, "med", 30, 820)
    sw = d.textlength(sub, font=fs)
    d.text((W // 2, 518), sub, font=fs, fill=CREAM, anchor="mm")
    d.line((W // 2 - sw / 2 - 70, 518, W // 2 - sw / 2 - 18, 518), fill=MUTE + (150,), width=2)
    d.line((W // 2 + sw / 2 + 18, 518, W // 2 + sw / 2 + 70, 518), fill=MUTE + (150,), width=2)
    if pl.get("part"):
        tag = f"PART {pl['part']}"
        ft = F("bold", 24)
        tw = d.textlength(tag, font=ft)
        d.rounded_rectangle((W // 2 - tw / 2 - 18, 562, W // 2 + tw / 2 + 18, 600), 19, fill=RED + (235,))
        d.text((W // 2, 581), tag, font=ft, fill=WHITE, anchor="mm")


def backdrop(pl):
    """The dark map, faded into the header and the card, with the header on top."""
    try:
        from . import basemap
        base = basemap.draw((W, H), pl["to_px"], pl["from_px"], style=basemap.NIGHT, paper=basemap.NIGHT_PAPER)
        credit = basemap.ATTRIBUTION
    except Exception as e:  # no network or no tile reader: a plain dark field, so a batch never fails on the map
        print(f"basemap unavailable ({e}); drawing the plain night field", file=sys.stderr, flush=True)
        base, credit = Image.new("RGB", (W, H), BG), ""
    im = base.convert("RGB")
    d = ImageDraw.Draw(im, "RGBA")  # an RGB frame drawn in RGBA mode blends the alpha
    for y in range(H):  # night sky over the header; the map runs on to the bottom, dimmer under the card
        a = 255 if y < 580 else int(255 * (680 - y) / 100) if y < 680 else 0
        a = max(a, min(150, int(150 * (y - 1320) / 200)) if y > 1320 else 0)
        if a:
            d.line((0, y, W, y), fill=BG + (min(255, a),))
    header(im, pl)
    if credit:
        d.text((FIT[0], 1470), credit, font=F("med", 19), fill=MUTE + (220,), stroke_width=3, stroke_fill=BG)
    return im, credit


def route_points(xy, step=10):
    pts = []
    for a, b in zip(xy, xy[1:]):
        n = max(1, int(math.dist(a, b) // step))
        pts += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n + 1)]
    return pts


def overlay(pl):
    """Everything that sits on the route and never moves: the Metro badge, the medallions with their pins and names."""
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(top, "RGBA")
    xy, off = pl["xy"], pl["off"]
    pts = route_points(xy)
    taken = [(x - 22, y - 40, x + 36, y + 12) for x, y in xy[off:]]  # the stop icons and their number badges
    st = pl["station"]
    if st:
        x, y = xy[0]
        c = LINE_RGB.get(st.get("line"), (104, 116, 140))  # a suburban rail start is grey with an R
        top.alpha_composite(glow((W, H), lambda dd, k: dd.ellipse(((x - 40) * k, (y - 40) * k, (x + 40) * k, (y + 40) * k), fill=c + (190,)), blur=14))
        d.rounded_rectangle((x - 26, y - 26, x + 26, y + 26), 11, fill=c, outline=WHITE, width=3)
        d.text((x, y + 2), "M" if st.get("line") in LINE_RGB else "R", font=F("bold", 30), fill=WHITE, anchor="mm")
        name = station_name(st)
        f = F("bold", 22)
        tw = d.textlength(name, font=f)
        cands = [(x - tw / 2, y + 32), (x - tw / 2, y - 60), (x + 34, y - 12), (x - 34 - tw, y - 12)]
        r = min(((min(max(cx, 40), 900 - tw), cy, min(max(cx, 40), 900 - tw) + tw, cy + 26) for cx, cy in cands),
                key=lambda r: sum(1 for px, py in pts if r[0] < px < r[2] and r[1] < py < r[3]) * 50 + sum(overlap(r, o) for o in taken))
        taken += [(x - 30, y - 30, x + 30, y + 30), r]
        pl["st_label"] = (name, f, r, c)
    meds, credits = [], []
    for i in pl["lit"]:
        p = pl["order"][i]
        try:
            m = medallion(p)
        except Exception as e:
            print(f"no photo for {p['id']} ({e})", file=sys.stderr, flush=True)
            continue
        fw, fh = m.width - 2 * PAD, m.height - 2 * PAD
        q = xy[off + i]
        r = place(q, (fw, fh), pts, taken)
        taken.append(r)
        meds.append((p, m, r, q))
        ph = photo_of(p)
        credits.append((ph[1], ph[2]))
    pl["walker_at"] = walker_spot(xy, [m[2] for m in meds] + taken)
    return top, meds, credits


def draw_medallions(im, meds, pl):
    d = ImageDraw.Draw(im, "RGBA")
    for p, m, r, q in meds:  # a gold pin from the frame to its stop, under the frame
        fx = min(max(q[0], r[0] + 20), r[2] - 20)
        fy = r[1] + (m.height - 2 * PAD) if q[1] > r[1] + (m.height - 2 * PAD) else r[1] + 40 if q[1] < r[1] else q[1]
        d.line([q, (fx, fy)], fill=GOLD + (230,), width=3)
    for p, m, r, q in meds:
        comp(im, m, (r[0] - PAD, r[1] - PAD))
        d = ImageDraw.Draw(im, "RGBA")
        name = short_name(p)
        w = r[2] - r[0]
        f = fit(d, name, "bold", 24, w + 50, minsize=16)
        d.text(((r[0] + r[2]) / 2, r[3] - 18), name, font=f, fill=WHITE, anchor="mm", stroke_width=4, stroke_fill=BG)
    if pl.get("st_label"):
        name, f, r, c = pl["st_label"]
        d.text((r[0], r[1]), name, font=f, fill=(150, 196, 255), stroke_width=4, stroke_fill=BG)


def walker_spot(xy, boxes):
    """For the cover: the point on the route farthest from every medallion and label, where the walker stands."""
    best = None
    for p in route_points(xy, 14):
        if not (FIT[0] < p[0] < FIT[2] and FIT[1] + 60 < p[1] < FIT[3]):
            continue
        me = (p[0] - 24, p[1] - 80, p[0] + 24, p[1] + 8)  # the figure stands on the line
        dd = min(max(r[0] - me[2], 0, me[0] - r[2]) + max(r[1] - me[3], 0, me[1] - r[3]) for r in boxes) if boxes else 999
        if best is None or dd > best[1]:
            best = (p, dd)
    return best[0] if best else xy[len(xy) // 2]


def path_to(pl, prog):
    """The route from the Metro up to prog stops reached (fractional), and the point at its head."""
    xy, off = pl["xy"], pl["off"]
    reached = min(float(len(pl["order"])), max(0.0, prog))
    full, frac = int(reached), reached - int(reached)
    last = off + full - 1 if (off or full) else 0
    if off == 0 and full == 0:
        return [xy[0]], xy[0]
    path = list(xy[:last + 1])
    if last + 1 < len(xy) and frac > 0:
        a, b, u = xy[last], xy[last + 1], ease(frac)
        path.append((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u))
    return path, path[-1]


def card(d, title, sub, a=1.0):
    y0 = 1322
    d.rounded_rectangle((70, y0, 920, y0 + 116), 26, fill=(22, 14, 18, int(236 * a)), outline=RED + (int(180 * a),), width=2)
    d.text((104, y0 + 20), title, font=fit(d, title, "bold", 40, 780), fill=WHITE + (int(255 * a),))
    d.text((104, y0 + 72), sub, font=fit(d, sub, "med", 30, 780), fill=GOLD + (int(255 * a),))


def frame(base, top, meds, pl, t):
    im = base.copy()
    xy, off, order = pl["xy"], pl["off"], pl["order"]
    n = len(order)
    full_path = list(xy)
    if t < pl["t_dim"]:  # the cover: the whole walk lit
        prog, path, head, a_full = n, full_path, None, 1.0
    else:
        a_full = 0.22 if t >= pl["t_draw"] else 1.0 - 0.78 * ease((t - pl["t_dim"]) / (pl["t_draw"] - pl["t_dim"]))
        prog = (t - pl["t_draw"]) / pl["per"] if t >= pl["t_draw"] else 0.0
        path, head = path_to(pl, prog) if t >= pl["t_draw"] else ([xy[0]], xy[0])
    neon(im, full_path, a=a_full)
    if t >= pl["t_dim"]:
        neon(im, path, a=1.0)
    d = ImageDraw.Draw(im, "RGBA")
    for i in range(n):
        q = xy[off + i]
        done = prog >= i + 1 - 0.12
        if i in pl["lit"]:
            dot(d, q, r=10 if done else 8, a=255 if done else 190)
            continue
        pop = 1.0 if not (t >= pl["t_draw"] and done) else min(1.0, 0.6 + (prog - i) * 2)
        lamp(im, q, i + 1 if (done and t >= pl["t_draw"]) else None, a=1.0 if done else 0.62 * pop + 0.2)
        d = ImageDraw.Draw(im, "RGBA")
    comp(im, top)
    draw_medallions(im, meds, pl)
    d = ImageDraw.Draw(im, "RGBA")
    if t < pl["t_dim"]:  # on the cover the walker strolls the emptiest stretch of the route
        walker(d, (pl["walker_at"][0], pl["walker_at"][1] + 8), phase=0.9, s=1.15)
    elif head is not None:
        walker(d, (head[0], head[1] + 6), phase=t * 9, s=1.0)
    st = pl["station"]
    st_name = station_name(st) if st else ""
    if pl["t_dim"] <= t < pl["t_draw"] + 0.3 and st:
        card(d, f"Start: {st_name}", "Get off here and follow the red line", ease((t - pl["t_dim"]) / 0.4))
    elif pl["t_draw"] + 0.3 <= t < pl["t_hold"]:
        k = min(n, max(1, int(prog + 0.12)))
        card(d, f"{k} · {order[k - 1]['name']}", f"{pl['km'][off + k - 1]:.1f} km walked  ·  stop {k} of {n}")
    elif t >= pl["t_hold"]:
        card(d, f"~{round(pl['steps'], -2):,} steps  ·  ~{round(pl['walk_min'] / 60, 1):g} h walking",
             f"Best for: {pl['best']}" if pl["best"] else f"Start at {st_name}")
    return im.convert("RGB")


def end_frame(pl, t, credits, map_credit):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im, "RGBA")
    a = int(255 * ease(t / 0.4))
    cx = W // 2 - 50
    d.text((cx, 520), "SAVE THIS", font=F("display", 150), fill=WHITE + (a,), anchor="mm")
    d.text((cx, 680), "ROUTE", font=F("display", 150), fill=RED + (a,), anchor="mm")
    d.text((cx, 820), "সেভ করে রাখুন, পুজোয় কাজে লাগবে", font=F("bnb", 46), fill=CREAM + (a,), anchor="mm")
    y = 940
    if pl.get("next"):
        nx = f"Part {(pl.get('part') or 1) + 1}: {pl['next']}, next"
        d.rounded_rectangle((cx - d.textlength(nx, font=F("bold", 36)) / 2 - 26, y - 34, cx + d.textlength(nx, font=F("bold", 36)) / 2 + 26, y + 34), 34, fill=RED + (int(a * 0.92),))
        d.text((cx, y), nx, font=F("bold", 36), fill=WHITE + (a,), anchor="mm")
        y += 110
    d.text((cx, y), "Comment “PUJO” for every area route", font=F("semi", 38), fill=GOLD + (a,), anchor="mm")
    d.text((cx, y + 60), HANDLE, font=F("semi", 36), fill=MUTE + (a,), anchor="mm")
    people = sorted({c[0] for c in credits if c[0]})
    lines = []
    if people:
        lic = sorted({c[1] for c in credits if c[1]})
        lines.append(f"Photos: {', '.join(people)} ({', '.join(lic)}), Wikimedia Commons")
    if map_credit:
        lines.append(map_credit)
    lines.append(AUDIO_CREDIT)
    yy = 1330
    for s in lines:
        f = fit(d, s, "med", 22, 860, minsize=14)
        d.text((cx, yy), s, font=f, fill=MUTE + (int(a * 0.85),), anchor="mm")
        yy += 34
    return im


def render(zone_id=None, out=None, g=None, ids=None, title=None, title_bn=None, area=None, part=None, nxt=None, hook=None,
           ordered=False, end_secs=3.2):
    g = g or json.loads((ROOT / "app" / "data" / "guide.json").read_text(encoding="utf-8"))
    pl = plan(zone_id, g, ids, title, title_bn, area, part, nxt, ordered)
    pl["hook"] = hook
    base, map_credit = backdrop(pl)
    top, meds, credits = overlay(pl)
    total = pl["t_end"] + end_secs
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-ss", "2", "-i", str(AUDIO), "-t", f"{total:.2f}",
           "-af", f"afade=t=in:d=0.3,afade=t=out:st={total - 1.2:.2f}:d=1.2,volume=0.9",
           "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
           "-c:a", "aac", "-b:a", "160k", "-shortest", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    ends, cover = {}, None
    for f in range(int(total * FPS)):
        t = f / FPS
        if t < pl["t_dim"]:
            cover = cover or frame(base, top, meds, pl, 0.0)  # the cover holds still, so it renders once
            im = cover
        elif t < pl["t_end"]:
            im = frame(base, top, meds, pl, t)
        else:
            k = min(f - int(pl["t_end"] * FPS), 12)
            if k not in ends:
                ends[k] = end_frame(pl, k / FPS, credits, map_credit)
            im = ends[k]
        p.stdin.write(im.tobytes())
    p.stdin.close()
    if p.wait():
        raise SystemExit(f"ffmpeg failed for {out}")
    return round(total, 2), pl


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--zone")
    ap.add_argument("--ids", help="comma-separated pandal ids for a themed route (with --title)")
    ap.add_argument("--title")
    ap.add_argument("--title-bn")
    ap.add_argument("--area", help="the area as the headline names it, e.g. 'North Kolkata'")
    ap.add_argument("--part", type=int)
    ap.add_argument("--next", help="the next part's area, named on the end frame")
    ap.add_argument("--ordered", action="store_true")
    ap.add_argument("--out", required=True)
    ap.add_argument("--still", type=float, help="write one frame at this time (s) as a JPEG instead of the video")
    a = ap.parse_args(argv)
    ids = [i.strip() for i in a.ids.split(",") if i.strip()] if a.ids else None
    if not (a.zone or ids):
        ap.error("--zone or --ids")
    if a.still is not None:
        pl = plan(a.zone, None, ids, a.title, a.title_bn, a.area, a.part, a.next, a.ordered)
        base, map_credit = backdrop(pl)
        top, meds, credits = overlay(pl)
        im = frame(base, top, meds, pl, a.still) if a.still < pl["t_end"] else end_frame(pl, a.still - pl["t_end"], credits, map_credit)
        im.save(a.out, quality=90)
        return
    secs, pl = render(a.zone, a.out, ids=ids, title=a.title, title_bn=a.title_bn, area=a.area, part=a.part, nxt=a.next, ordered=a.ordered)
    print(f"{a.out}: {secs}s, {len(pl['order'])} stops")


if __name__ == "__main__":
    main()
