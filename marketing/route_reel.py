"""Animated route reel: one zone's walking route drawing itself on a light map, stop by stop, over the dhak.

    python -m marketing.route_reel --zone south_lakemarket --out out/r.mp4

The guide's own data (app/data/guide.json: zones[].route): the walking order, the Metro station to start from, the
distance and steps. Frame 1 already carries the hook ("15 PANDALS. 13 KM. ONE NIGHT."), the numbers count up, the
route then draws from the station through every numbered stop while a card names the stop and the running distance,
holds on the finished route with the facts, and ends on "Comment PUJO". A light paper look, so it stands out in a
feed of dark pandal photos. 1080x1920, 30 fps, text kept inside Instagram's safe area (y 200 to 1440, right rail clear).
Audio: the Commons dhak recording the app uses (credited in the caption). Needs Pillow and ffmpeg.
"""
import argparse
import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from .routes import BEST, F, ROOT, fit, project, spread

W, H, FPS = 1080, 1920, 30
PAPER, INK, RED, MUTE = (251, 243, 228), (34, 18, 12), (178, 24, 38), (120, 96, 80)
LINE_RGB = {"blue": (46, 110, 214), "green": (32, 150, 90), "purple": (128, 70, 170), "orange": (232, 120, 30),
            "yellow": (214, 170, 20), "pink": (214, 80, 150)}
MAP = (90, 700, 900, 1272)  # x0, y0, x1, y1: clear of the action rail on the right and the caption at the bottom
AUDIO = ROOT / "app" / "audio" / "dhak.mp3"
AUDIO_CREDIT = "Dhak: Sumita Roy Dutta (CC BY-SA 4.0), Wikimedia Commons"


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def plan(zone_id, g=None):
    """Everything the frames need for one zone: stops in walking order, pixel positions, timing."""
    g = g or json.loads((ROOT / "app" / "data" / "guide.json").read_text(encoding="utf-8"))
    Z = {z["id"]: z for z in g["zones"]}
    z = Z[zone_id]
    P = {p["id"]: p for p in g["pandals"]}
    T = {t["id"]: t for t in g["transit"]}
    r = z["route"]
    order = [P[i] for i in r["order"] if i in P]
    st = T.get(r.get("start")) or T.get(z.get("entry_station"))
    geo = ([(st["lat"], st["lng"])] if st else []) + [(p["lat"], p["lng"]) for p in order]
    pad = 70
    box = (MAP[0] + pad, MAP[1] + pad, MAP[2] - pad, MAP[3] - pad)
    xy = spread(project(geo, box), box, gap=64 if len(order) <= 12 else 56, fixed=1 if st else 0)
    # the same projection for the backdrop: other pandals and Metro stations inside the frame, faint
    lat0 = sum(p[0] for p in geo) / len(geo)
    xs = [p[1] * math.cos(math.radians(lat0)) for p in geo]
    ys = [-p[0] for p in geo]
    s = min((box[2] - box[0]) / max(1e-9, max(xs) - min(xs)), (box[3] - box[1]) / max(1e-9, max(ys) - min(ys)))
    ox = box[0] + ((box[2] - box[0]) - s * (max(xs) - min(xs))) / 2
    oy = box[1] + ((box[3] - box[1]) - s * (max(ys) - min(ys))) / 2
    to_px = lambda la, lo: (ox + (lo * math.cos(math.radians(lat0)) - min(xs)) * s, oy + (-la - min(ys)) * s)
    inside = lambda q: MAP[0] + 10 < q[0] < MAP[2] - 10 and MAP[1] + 10 < q[1] < MAP[3] - 10
    others = [q for q in (to_px(p["lat"], p["lng"]) for p in g["pandals"] if p["id"] not in r["order"]) if inside(q)]
    metro = {}
    for t in g["transit"]:
        q = to_px(t["lat"], t["lng"])
        if inside(q):
            metro.setdefault(t.get("line", "blue"), []).append(q)
    legs = [hav(a, b) for a, b in zip(geo, geo[1:])]
    scale = r["walk_m"] / max(1.0, sum(legs))  # the guide's walking distance, shared out along the legs
    km = [0.0]
    for leg in legs:
        km.append(km[-1] + leg * scale / 1000)
    per = min(1.0, max(0.55, 11.0 / max(1, len(order))))
    return {"zone": z, "route": r, "order": order, "station": st, "xy": xy, "others": others, "metro": metro,
            "km": km, "per": per, "t_route": 2.2, "t_hold": 2.2 + per * len(order), "best": BEST.get(zone_id, "")}


def backdrop(pl):
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im, "RGBA")
    for x in range(MAP[0], MAP[2] + 1, 54):  # a faint street-grid feel, not a real map
        d.line((x, MAP[1], x, MAP[3]), fill=(230, 214, 190, 120), width=2)
    for y in range(MAP[1], MAP[3] + 1, 54):
        d.line((MAP[0], y, MAP[2], y), fill=(230, 214, 190, 120), width=2)
    for line, pts in pl["metro"].items():
        c = LINE_RGB.get(line, (46, 110, 214))
        for q in pts:
            d.ellipse((q[0] - 7, q[1] - 7, q[0] + 7, q[1] + 7), fill=c + (90,))
    for q in pl["others"]:
        d.ellipse((q[0] - 6, q[1] - 6, q[0] + 6, q[1] + 6), fill=(178, 24, 38, 45))
    return im


def header(d, pl, t):
    n, r = len(pl["order"]), pl["route"]
    # the real numbers from frame 1 (the hook has to read before anything moves)
    kick = f"PUJO PARIKRAMA · {pl['zone'].get('short', pl['zone']['name']).upper()} PUJO ROUTE"
    d.text((90, 222), kick, font=fit(d, kick, "semi", 30, 800), fill=RED)
    d.text((86, 262), f"{n} PANDALS.", font=F("display", 116), fill=INK)
    d.text((86, 382), f"{r['walk_m'] / 1000:.1f} KM.", font=F("display", 116), fill=RED)
    d.text((86, 502), "ONE NIGHT.", font=F("display", 116), fill=INK)
    bn = pl["zone"].get("short_bn") or pl["zone"].get("name_bn") or ""
    line = f"{bn} · এক রাতে, পায়ে হেঁটে" if bn else "এক রাতে, পায়ে হেঁটে"
    d.text((90, 640), line, font=fit(d, line, "bnb", 40, 800), fill=MUTE)


def pin(d, q, n, s=1.0, done=True):
    rad = 25 * s
    d.ellipse((q[0] - rad, q[1] - rad, q[0] + rad, q[1] + rad), fill=RED if done else PAPER, outline=INK, width=3)
    if s > 0.6:
        d.text((q[0], q[1] + 1), str(n), font=F("bold", int(26 * s)), fill=(255, 255, 255), anchor="mm")


def station(d, pl, t):
    st = pl["station"]
    if not st:
        return
    x, y = pl["xy"][0]
    a = ease((t - 1.0) / 0.5)
    if a <= 0:
        return
    d.rounded_rectangle((x - 30, y - 30, x + 30, y + 30), 12, fill=(46, 110, 214, int(255 * a)), outline=(255, 255, 255, int(255 * a)), width=4)
    d.text((x, y + 2), "M", font=F("bold", 34), fill=(255, 255, 255, int(255 * a)), anchor="mm")


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
    # the line runs station -> stop 1 -> stop 2 ...; the stop being walked to gets a partial segment
    reached = min(float(len(order)), max(0.0, prog))
    full, frac = int(reached), reached - int(reached)
    last = off + full - 1  # index in xy of the last point fully reached (the station counts from the start)
    path = list(xy[:last + 1]) if last >= 0 else []
    if last >= 0 and last + 1 < len(xy) and frac > 0:
        a, b, u = xy[last], xy[last + 1], ease(frac)
        path.append((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u))
    if len(path) > 1:
        d.line(path, fill=RED, width=9, joint="curve")
    station(d, pl, t)
    for i in range(len(order)):
        q = xy[off + i]
        if prog >= i + 1 - 0.15:  # pops in as the line arrives
            s = 0.6 + 0.4 * ease((prog - i - 0.85) / 0.3)
            pin(d, q, i + 1, s)
        elif t > pl["t_route"] - 0.6:
            d.ellipse((q[0] - 8, q[1] - 8, q[0] + 8, q[1] + 8), fill=(178, 24, 38, 90))
    st_name = (st["name"].replace(" Sutanuti", "") + " Metro") if st else ""
    if t < pl["t_route"]:
        if st and t > 1.0:
            card(d, f"Start: {st_name}", "Get off here and follow the numbers", ease((t - 1.0) / 0.5))
    elif t < pl["t_hold"]:
        k = min(len(order), max(1, int(prog + 0.15)))  # the stop whose pin has popped
        card(d, f"{k} · {order[k - 1]['name']}", f"{pl['km'][k]:.1f} km walked  ·  stop {k} of {len(order)}")
    else:
        r = pl["route"]
        card(d, f"~{round(r['steps'], -2):,} steps  ·  ~{round(r['walk_min'] / 60, 1):g} h walking",
             f"Best for: {pl['best']}" if pl["best"] else f"Start at {st_name}")
    return im


def end_frame(pl, t):
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im, "RGBA")
    a = ease(t / 0.4)
    d.text((W // 2 - 70, 560), "COMMENT", font=F("display", 150), fill=INK + (int(255 * a),), anchor="mm")
    d.text((W // 2 - 70, 760), "“PUJO”", font=F("display", 230), fill=RED + (int(255 * a),), anchor="mm")
    for k, s in enumerate(["for all 9 area routes,", "the Metro stops and live quiet hours"]):
        d.text((W // 2 - 70, 930 + k * 60), s, font=F("semi", 44), fill=INK + (int(255 * a),), anchor="mm")
    d.text((W // 2 - 70, 1080), "কমেন্টে লিখুন “পুজো”, রুট পাঠিয়ে দেব!", font=F("bnb", 50), fill=RED + (int(255 * a),), anchor="mm")
    d.text((W // 2 - 70, 1250), "@pujoparikrama.guide", font=F("semi", 40), fill=MUTE + (int(255 * a),), anchor="mm")
    return im


def render(zone_id, out, end_secs=3.0, g=None):
    pl = plan(zone_id, g)
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
    for f in range(int(total * FPS)):
        t = f / FPS
        im = frame(base, pl, t) if t < t_end else end_frame(pl, t - t_end)
        p.stdin.write(im.tobytes())
    p.stdin.close()
    if p.wait():
        raise SystemExit(f"ffmpeg failed for {out}")
    return round(total, 2), pl


def caption(c):
    """Plan caption (bn, en, tags) plus the audio credit the CC BY-SA licence asks for."""
    parts = [c.get("bn", ""), c.get("en", ""), c.get("tags", ""), f"🎵 {AUDIO_CREDIT}. Routes: Pujo Parikrama guide data."]
    return "\n\n".join(x.strip() for x in parts if x and x.strip())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--zone", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--still", type=float, help="write one frame at this time (s) as a JPEG instead of the video")
    a = ap.parse_args(argv)
    if a.still is not None:
        pl = plan(a.zone)
        base = backdrop(pl)
        t_end = pl["t_hold"] + 2.6
        im = frame(base, pl, a.still) if a.still < t_end else end_frame(pl, a.still - t_end)
        im.save(a.out, quality=88)
        return
    secs, pl = render(a.zone, a.out)
    print(f"{a.out}: {secs}s, {len(pl['order'])} stops")


if __name__ == "__main__":
    main()
