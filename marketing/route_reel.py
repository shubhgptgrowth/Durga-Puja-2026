"""Animated route reel: a walking route drawing itself on a real street map, stop by stop, over the dhak.

    python -m marketing.route_reel --zone salt_lake --out out/r.mp4
    python -m marketing.route_reel --ids bagbazar,kumartuli,ahiritola --title "Bonedi Bari" --out out/b.mp4
    python -m marketing.route_reel --zone salt_lake --still 0 --out cover.jpg      # one frame (0 = the cover)

A zone route comes from the guide (app/data/guide.json: zones[].route): the walking order, the Metro station to start
from, the distance and steps. A themed route is a list of pandal ids and a title: it starts at the Metro station
nearest any of them and walks to the nearest unvisited pandal each time (--ordered keeps the given order), with the
distance worked out the way the guide does (straight line x 1.3 for the lanes).

Frame 1 is the cover and already carries the hook ("SALT LAKE PUJO ROUTE / 7 PANDALS. / 7.9 KM. / ONE NIGHT.") on a
street map (marketing/basemap.py, OpenStreetMap via Protomaps) with a pandal icon and name at every stop and the Metro
start marked. The route then draws from the station through every stop while a card names it and the running
distance, holds on the finished route, and ends on "Comment PUJO". Our handle and domain sit inside the map itself.
1080x1920, 30 fps, text inside Instagram's safe area (y 200 to 1440, right rail clear). Audio: the Commons dhak the
app uses (credited on the end frame). Needs Pillow (with raqm), ffmpeg, pmtiles and mapbox-vector-tile.
"""
import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from .routes import BEST, F, ROOT, fit, overlap, place_label, spread

W, H, FPS = 1080, 1920, 30
PAPER, INK, RED, MUTE = (251, 243, 228), (34, 18, 12), (178, 24, 38), (120, 96, 80)
GOLD = (242, 184, 80)
LINE_RGB = {"blue": (46, 110, 214), "green": (32, 150, 90), "purple": (128, 70, 170), "orange": (232, 120, 30),
            "yellow": (214, 170, 20), "pink": (214, 80, 150)}
MAP = (100, 790, 920, 1250)  # where the route is fitted: clear of the header, the right-hand action rail and the card
LABELS = (36, 770, 1000, 1250)  # where pandal names may go (above the handle line and the card)
AUDIO = ROOT / "app" / "audio" / "dhak.mp3"
AUDIO_CREDIT = "Dhak: Sumita Roy Dutta (CC BY-SA 4.0), Wikimedia Commons"
HANDLE, DOMAIN = "@pujoparikramaguide.in", "pujoparikramaguide.in"
DETOUR, PACE_M_MIN, STEPS_PER_M = 1.3, 3200 / 60, 1.46  # as the guide computes walks (scripts/seo/metro.py walk())
SUFFIX = re.compile(r"\s+(Sarbojanin(\s+Durg\w+)?|Durgotsab|Durgotsav|Puja Committee|Durga Puja)$", re.I)


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def short_name(p, area=""):
    n = SUFFIX.sub("", p["name"]).strip() or p["name"]
    if area and n.lower().endswith(" " + area.lower()) and len(n) > len(area) + 3:
        n = n[: -len(area)].strip()
    return n


def route(g, zone_id=None, ids=None, title=None, title_bn=None, ordered=False):
    """The stops in walking order, the start station and the walk's numbers, for a zone or a themed list."""
    P = {p["id"]: p for p in g["pandals"]}
    T = {t["id"]: t for t in g["transit"]}
    ll = lambda p: (p["lat"], p["lng"])
    if zone_id:
        z = {z["id"]: z for z in g["zones"]}[zone_id]
        r = z["route"]
        short = z.get("short") or z["name"]
        return {"key": zone_id, "area": short, "title": title or f"{short} Pujo Route", "title_bn": title_bn or z.get("short_bn") or z.get("name_bn") or "",
                "order": [P[i] for i in r["order"] if i in P], "station": T.get(r.get("start")) or T.get(z.get("entry_station")),
                "walk_m": r["walk_m"], "walk_min": r["walk_min"], "steps": r["steps"], "best": BEST.get(zone_id, "")}
    missing = [i for i in ids if i not in P]
    if missing:
        raise SystemExit(f"unknown pandal ids: {', '.join(missing)}")
    stops = [P[i] for i in ids]
    metro = [t for t in g["transit"] if t.get("line") in LINE_RGB]
    near = lambda p: min(metro, key=lambda t: hav(ll(p), ll(t)))
    if not ordered:  # start at the pandal closest to a Metro station, then always walk to the nearest one left
        first = min(stops, key=lambda p: hav(ll(p), ll(near(p))))
        tour, left = [first], [p for p in stops if p is not first]
        while left:
            nxt = min(left, key=lambda p: hav(ll(tour[-1]), ll(p)))
            tour.append(nxt)
            left.remove(nxt)
        stops = tour
    st = near(stops[0])
    geo = [ll(st)] + [ll(p) for p in stops]
    walk_m = round(sum(hav(a, b) for a, b in zip(geo, geo[1:])) * DETOUR)
    return {"key": "custom", "area": "", "title": title or "Pujo Route", "title_bn": title_bn or "", "order": stops, "station": st,
            "walk_m": walk_m, "walk_min": round(walk_m / PACE_M_MIN), "steps": round(walk_m * STEPS_PER_M), "best": ""}


def hook_line3(hook):
    """'17 pandals. 11 km. One night.' -> 'ONE NIGHT.' (the numbers always come from the data)."""
    m = re.match(r"\s*\d+\s+\w+\.\s*[\d.]+\s*km\.\s*(.+)$", hook or "", re.I)
    return (m.group(1).strip() if m else "One night.").upper()


def plan(zone_id=None, g=None, ids=None, title=None, title_bn=None, hook=None, ordered=False):
    """Everything the frames need: stops in walking order, the projection, icon and label positions, timing."""
    g = g or json.loads((ROOT / "app" / "data" / "guide.json").read_text(encoding="utf-8"))
    rt = route(g, zone_id, ids, title, title_bn, ordered)
    order, st = rt["order"], rt["station"]
    geo = ([(st["lat"], st["lng"])] if st else []) + [(p["lat"], p["lng"]) for p in order]
    pad = 40
    box = (MAP[0] + pad, MAP[1] + pad, MAP[2] - pad, MAP[3] - pad)
    lat0 = sum(p[0] for p in geo) / len(geo)
    c0 = math.cos(math.radians(lat0))
    xs, ys = [p[1] * c0 for p in geo], [-p[0] for p in geo]
    # equal scale on both axes (true shape); never zoomed in past ~450 m across the map
    s = min((box[2] - box[0]) / max(0.004, max(xs) - min(xs)), (box[3] - box[1]) / max(0.004, max(ys) - min(ys)))
    ox = box[0] + ((box[2] - box[0]) - s * (max(xs) - min(xs))) / 2
    oy = box[1] + ((box[3] - box[1]) - s * (max(ys) - min(ys))) / 2
    to_px = lambda la, lo: (ox + (lo * c0 - min(xs)) * s, oy + (-la - min(ys)) * s)
    from_px = lambda x, y: (-((y - oy) / s + min(ys)), ((x - ox) / s + min(xs)) / c0)
    true = [to_px(*q) for q in geo]
    xy = spread(true, box, gap=50, fixed=1 if st else 0)  # nudge stops that sit on top of each other
    metro = []
    for t in g["transit"]:
        q = to_px(t["lat"], t["lng"])
        if t.get("line") in LINE_RGB and LABELS[0] < q[0] < LABELS[2] and LABELS[1] < q[1] < LABELS[3] and t is not st:
            metro.append((q, LINE_RGB[t["line"]]))
    legs = [hav(a, b) for a, b in zip(geo, geo[1:])]
    scale = rt["walk_m"] / max(1.0, sum(legs))  # the walking distance, shared out along the legs
    km = [0.0]
    for leg in legs:
        km.append(km[-1] + leg * scale / 1000)
    # pandal names beside their icons, placed clear of every icon and of each other
    d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    off = 1 if st else 0
    obstacles = [(x - 30, y - 36, x + 30, y + 22) for x, y in xy]
    st_label = None
    if st:
        name = st["name"].replace(" Sutanuti", "") + " Metro"
        f = F("bold", 24)
        bb = d.textbbox((0, 0), name, font=f)
        st_label = (name, f, place_label(xy[0], (bb[2] - bb[0] + 12, bb[3] - bb[1] + 10), obstacles, LABELS, gap=40))
        obstacles.append(st_label[2])
    walk = []  # points along the route line, so names avoid sitting on it
    for a, b in zip(xy, xy[1:]):
        n = max(1, int(math.dist(a, b) // 12))
        walk += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n)]
    labels = []
    for i, p in enumerate(order):
        name = short_name(p, rt["area"])
        best = None
        for size in (26, 23, 20):  # a smaller name beats one sitting on another
            f, fn = F("semi", size), F("bold", size)
            num = str(i + 1)
            w = d.textlength(num, font=fn) + 8 + d.textlength(name, font=f) + 12
            h = size + 14
            r, cost = spot(xy[off + i], (w, h), obstacles, walk)
            cost += (26 - size) * 40
            if best is None or cost < best[0]:
                best = (cost, (num, name, fn, f, r))
        obstacles.append(best[1][4])
        labels.append(best[1])
    per = min(1.0, max(0.55, 11.0 / max(1, len(order))))
    return {**rt, "zone": {"id": rt["key"], "name": rt["title"]}, "route": {"walk_m": rt["walk_m"], "walk_min": rt["walk_min"],
            "steps": rt["steps"]}, "xy": xy, "metro": metro, "labels": labels, "km": km, "per": per, "to_px": to_px,
            "from_px": from_px, "st_label": st_label, "line3": hook_line3(hook), "t_route": 2.2, "t_hold": 2.2 + per * len(order)}


def spot(anchor, size, obstacles, walk):
    """The least crowded place for a label of size (w, h) near anchor: beside, above or below the icon, near first."""
    (x, y), (w, h) = anchor, size
    best = None
    for gap in (30, 56, 92):
        for cx, cy in ((x + gap, y - h / 2), (x - gap - w, y - h / 2), (x - w / 2, y - gap - h - 10), (x - w / 2, y + gap),
                       (x + gap - 8, y - gap - h), (x + gap - 8, y + gap - 10), (x - gap - w + 8, y - gap - h), (x - gap - w + 8, y + gap - 10)):
            cx, cy = min(max(LABELS[0], cx), LABELS[2] - w), min(max(LABELS[1], cy), LABELS[3] - h)
            r = (cx, cy, cx + w, cy + h)
            cost = sum(overlap(r, o) for o in obstacles) + 60 * sum(1 for px, py in walk if r[0] < px < r[2] and r[1] < py < r[3])
            cost += gap * 6
            if best is None or cost < best[1]:
                best = (r, cost)
    return best


def watermark(im):
    """The domain, large and faint, across the map: a crop or a re-upload still carries our name."""
    lay = Image.new("RGBA", (1400, 220), (0, 0, 0, 0))
    ImageDraw.Draw(lay).text((700, 110), DOMAIN, font=F("display", 120), fill=MUTE + (16,), anchor="mm")
    lay = lay.rotate(18, expand=True)
    im.alpha_composite(lay, ((W - lay.width) // 2, (MAP[1] + MAP[3]) // 2 - lay.height // 2))


def backdrop(pl):
    try:
        from . import basemap
        base = basemap.draw((W, H), pl["to_px"], pl["from_px"])
        places, credit = base.info.get("places", []), basemap.ATTRIBUTION
    except Exception as e:  # no network or no tile reader: the paper grid, so a batch never fails on the map
        print(f"basemap unavailable ({e}); drawing the plain paper map", file=sys.stderr, flush=True)
        base, places, credit = Image.new("RGB", (W, H), PAPER), [], ""
        gd = ImageDraw.Draw(base)
        for x in range(0, W, 54):
            gd.line((x, MAP[1] - 60, x, MAP[3] + 40), fill=(234, 220, 198), width=2)
        for y in range(MAP[1] - 60, MAP[3] + 40, 54):
            gd.line((0, y, W, y), fill=(234, 220, 198), width=2)
    im = base.convert("RGBA")
    d = ImageDraw.Draw(im, "RGBA")
    taken = [lb[4] for lb in pl["labels"]] + [(x - 34, y - 40, x + 34, y + 26) for x, y in pl["xy"]] + ([pl["st_label"][2]] if pl["st_label"] else [])
    for name, (x, y) in places:  # neighbourhood names, faint, where they don't fight the pandal names
        f = F("med", 22)
        w = d.textlength(name.upper(), font=f)
        r = (x - w / 2, y - 14, x + w / 2, y + 14)
        if LABELS[1] < y < LABELS[3] and not any(r[0] < o[2] and o[0] < r[2] and r[1] < o[3] and o[1] < r[3] for o in taken):
            d.text((x, y), name.upper(), font=f, fill=MUTE + (150,), anchor="mm")
            taken.append(r)
    watermark(im)
    # the paper fades in over the map behind the header, and again under the stop card
    for y in range(0, 790):
        a = 255 if y < 700 else int(255 * (790 - y) / 90)
        d.line((0, y, W, y), fill=PAPER + (a,))
    for q, c in pl["metro"]:  # other Metro stations in view
        d.rounded_rectangle((q[0] - 11, q[1] - 11, q[0] + 11, q[1] + 11), 5, fill=c + (230,), outline=(255, 255, 255), width=2)
        d.text((q[0], q[1] + 1), "M", font=F("bold", 14), fill=(255, 255, 255), anchor="mm")
    d.text((MAP[0], 1258), f"{HANDLE}  ·  {DOMAIN}", font=F("semi", 24), fill=RED, stroke_width=4, stroke_fill=PAPER)
    if credit:
        d.text((MAP[0], 1428), credit, font=F("med", 20), fill=INK, stroke_width=3, stroke_fill=PAPER)
    return im.convert("RGB")


def header(d, pl, t):
    n = len(pl["order"])
    kick = f"PUJO PARIKRAMA · {pl['title'].upper()}"
    d.text((90, 222), kick, font=fit(d, kick, "semi", 34, 840), fill=RED)
    d.text((86, 266), f"{n} PANDALS.", font=F("display", 116), fill=INK)
    d.text((86, 386), f"{pl['walk_m'] / 1000:.1f} KM.", font=F("display", 116), fill=RED)
    d.text((86, 506), pl["line3"], font=fit(d, pl["line3"], "display", 116, 880), fill=INK)
    bn = pl.get("title_bn") or ""
    when = "এক সন্ধ্যায়" if "EVENING" in pl["line3"] else "এক দিনে" if "DAY" in pl["line3"] else "এক রাতে"
    line = f"{bn} · {when}, পায়ে হেঁটে" if bn else f"{when}, পায়ে হেঁটে"
    d.text((90, 640), line, font=fit(d, line, "bnb", 40, 800), fill=MUTE)


def pandal(d, q, n=None, a=255):
    """A small pandal: gold body, red roof, dark doorway; the stop number in a badge once the route reaches it."""
    x, y = q
    d.polygon([(x - 22, y - 2), (x, y - 26), (x + 22, y - 2)], fill=RED + (a,), outline=INK + (a,))
    d.ellipse((x - 4, y - 33, x + 4, y - 25), fill=GOLD + (a,), outline=INK + (a,))
    d.rectangle((x - 16, y - 2, x + 16, y + 18), fill=GOLD + (a,), outline=INK + (a,), width=2)
    d.rounded_rectangle((x - 6, y + 4, x + 6, y + 18), 5, fill=INK + (a,))
    if n is not None:
        d.ellipse((x + 8, y - 40, x + 40, y - 8), fill=INK, outline=(255, 255, 255), width=3)
        d.text((x + 24, y - 23), str(n), font=F("bold", 20 if n < 10 else 17), fill=(255, 255, 255), anchor="mm")


def station(d, pl, t):
    st = pl["station"]
    if not st:
        return
    x, y = pl["xy"][0]
    c = LINE_RGB.get(st.get("line"), (46, 110, 214))
    d.rounded_rectangle((x - 28, y - 28, x + 28, y + 28), 12, fill=c, outline=(255, 255, 255), width=4)
    d.text((x, y + 2), "M", font=F("bold", 32), fill=(255, 255, 255), anchor="mm")
    name, f, r = pl["st_label"]
    d.text((r[0] + 6, r[1] + 3), name, font=f, fill=c, stroke_width=4, stroke_fill=PAPER)


def card(d, title, sub, a=1.0):
    y0 = 1286
    d.rounded_rectangle((70, y0, 920, y0 + 128), 26, fill=(34, 18, 12, int(235 * a)))
    d.text((104, y0 + 26), title, font=fit(d, title, "bold", 40, 780), fill=(255, 255, 255, int(255 * a)))
    d.text((104, y0 + 80), sub, font=fit(d, sub, "med", 30, 780), fill=(255, 205, 41, int(255 * a)))


def frame(base, pl, t):
    im = base.copy()
    d = ImageDraw.Draw(im, "RGBA")
    header(d, pl, t)
    xy, order, st = pl["xy"], pl["order"], pl["station"]
    off = 1 if st else 0
    prog = (t - pl["t_route"]) / pl["per"]  # stops reached so far (fractional)
    reached = min(float(len(order)), max(0.0, prog))
    full, frac = int(reached), reached - int(reached)
    last = off + full - 1  # index in xy of the last point fully reached (the station counts from the start)
    path = list(xy[:last + 1]) if last >= 0 else []
    if last >= 0 and last + 1 < len(xy) and frac > 0:
        a, b, u = xy[last], xy[last + 1], ease(frac)
        path.append((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u))
    if len(path) > 1:
        d.line(path, fill=(255, 255, 255), width=17, joint="curve")
        d.line(path, fill=RED, width=10, joint="curve")
    for i in range(len(order)):  # every pandal is on the map from the cover; the number appears as the walk arrives
        done = prog >= i + 1 - 0.15
        pandal(d, xy[off + i], i + 1 if done else None, 255 if done or t < pl["t_route"] else 200)
    station(d, pl, t)
    for num, name, fn, f, r in pl["labels"]:
        d.text((r[0] + 6, r[1] + 4), num, font=fn, fill=RED, stroke_width=4, stroke_fill=PAPER)
        d.text((r[0] + 14 + d.textlength(num, font=fn), r[1] + 4), name, font=f, fill=INK, stroke_width=4, stroke_fill=PAPER)
    st_name = (st["name"].replace(" Sutanuti", "") + " Metro") if st else ""
    if t < pl["t_route"]:
        if st and t > 1.0:
            card(d, f"Start: {st_name}", "Get off here and follow the numbers", ease((t - 1.0) / 0.5))
    elif t < pl["t_hold"]:
        k = min(len(order), max(1, int(prog + 0.15)))
        card(d, f"{k} · {order[k - 1]['name']}", f"{pl['km'][k]:.1f} km walked  ·  stop {k} of {len(order)}")
    else:
        card(d, f"~{round(pl['steps'], -2):,} steps  ·  ~{round(pl['walk_min'] / 60, 1):g} h walking",
             f"Best for: {pl['best']}" if pl["best"] else f"Start at {st_name}")
    return im


def end_frame(pl, t, g=None):
    g = g or json.loads((ROOT / "app" / "data" / "guide.json").read_text(encoding="utf-8"))
    n = sum(1 for z in g["zones"] if len((z.get("route") or {}).get("order") or []) >= 4)
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im, "RGBA")
    a = ease(t / 0.4)
    d.text((W // 2 - 70, 560), "COMMENT", font=F("display", 150), fill=INK + (int(255 * a),), anchor="mm")
    d.text((W // 2 - 70, 760), "“PUJO”", font=F("display", 230), fill=RED + (int(255 * a),), anchor="mm")
    for k, s in enumerate([f"for all {n} area routes, the Metro stop", "for each, and food on the way"]):
        d.text((W // 2 - 70, 930 + k * 60), s, font=F("semi", 44), fill=INK + (int(255 * a),), anchor="mm")
    d.text((W // 2 - 70, 1080), "কমেন্টে লিখুন “পুজো”, রুট পাঠিয়ে দেব!", font=F("bnb", 50), fill=RED + (int(255 * a),), anchor="mm")
    d.text((W // 2 - 70, 1250), HANDLE, font=F("semi", 40), fill=MUTE + (int(255 * a),), anchor="mm")
    d.text((W // 2 - 70, 1700), AUDIO_CREDIT, font=F("med", 24), fill=MUTE + (int(200 * a),), anchor="mm")
    return im


def render(zone_id=None, out=None, end_secs=3.0, g=None, ids=None, title=None, title_bn=None, hook=None, ordered=False):
    g = g or json.loads((ROOT / "app" / "data" / "guide.json").read_text(encoding="utf-8"))
    pl = plan(zone_id, g, ids, title, title_bn, hook, ordered)
    t_end = pl["t_hold"] + 2.6
    total = t_end + end_secs
    base = backdrop(pl)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-ss", "2", "-i", str(AUDIO), "-t", f"{total:.2f}",
           "-af", f"afade=t=in:d=0.3,afade=t=out:st={total - 1.2:.2f}:d=1.2,volume=0.9",
           "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
           "-c:a", "aac", "-b:a", "160k", "-shortest", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    ends = {}
    for f in range(int(total * FPS)):
        t = f / FPS
        if t < t_end:
            im = frame(base, pl, t)
        else:
            k = min(f - int(t_end * FPS), 12)  # the end card only changes while it fades in
            if k not in ends:
                ends[k] = end_frame(pl, t - t_end, g)
            im = ends[k]
        p.stdin.write(im.tobytes())
    p.stdin.close()
    if p.wait():
        raise SystemExit(f"ffmpeg failed for {out}")
    return round(total, 2), pl


def caption(c):
    """The plan caption (marketing/captions.py); the dhak's CC BY-SA credit is on the end frame."""
    from .captions import compose
    return compose(c)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--zone")
    ap.add_argument("--ids", help="comma-separated pandal ids for a themed route (with --title)")
    ap.add_argument("--title")
    ap.add_argument("--title-bn")
    ap.add_argument("--hook", help="'N pandals. X km. One evening.': only the last phrase is used")
    ap.add_argument("--ordered", action="store_true", help="walk --ids in the given order")
    ap.add_argument("--out", required=True)
    ap.add_argument("--still", type=float, help="write one frame at this time (s) as a JPEG instead of the video")
    a = ap.parse_args(argv)
    ids = [i.strip() for i in a.ids.split(",") if i.strip()] if a.ids else None
    if not (a.zone or ids):
        ap.error("--zone or --ids")
    if a.still is not None:
        pl = plan(a.zone, None, ids, a.title, a.title_bn, a.hook, a.ordered)
        t_end = pl["t_hold"] + 2.6
        im = frame(backdrop(pl), pl, a.still) if a.still < t_end else end_frame(pl, a.still - t_end)
        im.save(a.out, quality=90)
        return
    secs, pl = render(a.zone, a.out, ids=ids, title=a.title, title_bn=a.title_bn, hook=a.hook, ordered=a.ordered)
    print(f"{a.out}: {secs}s, {len(pl['order'])} stops")


if __name__ == "__main__":
    main()
