"""Night-map route reel: the same walking route as marketing/route_reel.py, drawn as a glowing red line on a dark street
map, with the area's best-known pandals lit up as photo medallions and a walker who sets off from the Metro.

    python -m marketing.night_route --zone north --area "North Kolkata" --out out/n.mp4
    python -m marketing.night_route --zone north --area "North Kolkata" --part 1 --next "Central Kolkata" --out out/n.mp4
    python -m marketing.night_route --zone north --still 0 --out cover.jpg      # one frame (0 = the cover)
    python -m marketing.night_route --zone north --area "North Kolkata" --script  # the voiceover script, 5 lines

Frame 1 is the cover: "১৭টা পুজো · ১ রাতে" (the count from the guide), "<Area> Master Route" over a faded pujo photo,
the whole route glowing from the Metro start, the medallions and the walker. The camera then zooms in on the Metro and
follows the walker as the route redraws stop by stop along a smooth line (each stop ripples as it is reached, a card
names it with its photo and the distance so far, a bar counts the stops), pulls back out to the full lit route with
the walk's steps and hours, and ends on "Save this route" and "Comment PUJO" over the blurred map.

Voiceover: five lines per reel (script() writes them, in Bengali with an English gloss), recorded one file per line as
marketing/vo/night/<zone>/1.m4a ... 5.m4a (mp3, wav, ogg and aac work too). When they are there, each beat lasts as
long as its line and the dhak drops under the voice; without them the reel runs on the dhak alone. Every number comes
from app/data/guide.json; the photos are the pandals' own Wikimedia Commons photos (credited on the end frame with the
map and the dhak). 1080x1920, 30 fps, text inside Instagram's safe area. Needs Pillow (with raqm), ffmpeg, pmtiles
and mapbox-vector-tile.
"""
import argparse
import json
import math
import random
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .route_reel import AUDIO, AUDIO_CREDIT, HANDLE, LINE_RGB, ease, route, short_name
from .routes import F, ROOT, fetch, fit, overlap, spread

W, H, FPS = 1080, 1920, 30
SS = 2  # the map and the dim route are drawn at twice the frame size, so the camera can zoom in without blur
BG = (9, 11, 20)
WHITE, CREAM, MUTE = (255, 255, 255), (246, 232, 214), (172, 160, 160)
RED, RED_HI, GOLD = (255, 62, 62), (255, 190, 176), (255, 196, 92)
FIT = (120, 700, 880, 1240)  # where the route is fitted: under the header, clear of the right rail and the card
ANCHOR = (540, 1010)  # where the walker sits on screen while the camera follows him
ZOOM = 1.9
PAD = 30  # glow around a medallion frame
CACHE = Path.home() / ".cache" / "pujo-night-route"
VO_DIR = ROOT / "marketing" / "vo" / "night"
BN_NUM = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
BN_WORD = {1: "এক", 2: "দুই", 3: "তিন", 4: "চার", 5: "পাঁচ", 6: "ছয়", 7: "সাত", 8: "আট", 9: "নয়", 10: "দশ"}
# the series' areas and Metro starts as the voiceover says them (the guide has no Bengali station names)
AREA_BN = {"north": "উত্তর কলকাতা", "central": "মধ্য কলকাতা", "south_lakemarket": "লেক মার্কেট আর কালীঘাট",
           "south_gariahat": "গড়িয়াহাট আর বালিগঞ্জ", "southwest": "বেহালা আর নিউ আলিপুর", "lake_town_dumdum": "লেক টাউন আর দমদম",
           "bhowanipore": "ভবানীপুর আর এলগিন", "salt_lake": "সল্টলেক", "kasba": "কসবা", "jadavpur_santoshpur": "যাদবপুর আর সন্তোষপুর",
           "tolly_naktala": "টালিগঞ্জ আর নাকতলা", "howrah": "হাওড়া"}
STATION_BN = {"sovabazar": "শোভাবাজার", "mg_road": "এমজি রোড", "kalighat": "কালীঘাট", "ballygunge_rail": "বালিগঞ্জ",
              "behala_bazar": "বেহালা বাজার", "city_centre": "সিটি সেন্টার", "netaji_bhavan": "নেতাজি ভবন", "kavi_sukanta": "কবি সুকান্ত",
              "kavi_nazrul": "কবি নজরুল", "masterda_surya_sen": "মাস্টারদা সূর্য সেন", "liluah": "লিলুয়া"}
BN_SUFFIX = (" সার্বজনীন দুর্গোৎসব", " সার্বজনীন", " সর্বজনীন", " দুর্গোৎসব", " পুজো কমিটি")
# how the voiceover says the stops the guide has no Bengali name for (or whose Bengali reads oddly aloud)
BN_SAY = {"gariahat_sarbojanin_durgotsab": "গড়িয়াহাট", "adi_sammilati_sarbojanin": "আদি সম্মিলতি", "ae_block": "এ ই ব্লক",
          "salt_lake_ck": "সি কে ব্লক", "fd_block": "এফ ডি ব্লক", "bj_block": "বি জে ব্লক", "salt_lake_ia": "আই এ ব্লক",
          "salt_lake_ee": "ই ই ব্লক", "gouribari_sarbojanin": "গৌরীবাড়ি", "taltala_sarbojanin": "তালতলা"}
AUDIO_EXT = (".m4a", ".mp3", ".wav", ".ogg", ".opus", ".aac")


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


def photo(p, attempts=4):
    """The pandal's photo as an RGB image (cached); Commons answers 429 to bursts, so wait and retry."""
    for k in range(attempts):
        try:
            return ImageOps.exif_transpose(Image.open(fetch(photo_of(p)[0], CACHE))).convert("RGB")
        except OSError:
            if k == attempts - 1:
                raise
            time.sleep(6 * (k + 1))


def crop(src, w, h, cy=0.42):
    k = max(w / src.width, h / src.height)
    src = src.resize((max(w, round(src.width * k)), max(h, round(src.height * k))), Image.LANCZOS)
    left, top = (src.width - w) // 2, int((src.height - h) * cy)
    return src.crop((left, top, left + w, top + h))


# ---- voiceover ----------------------------------------------------------------------------------------------------

def bn_name(p):
    n = BN_SAY.get(p["id"]) or p.get("name_bn") or short_name(p)
    for s in BN_SUFFIX:
        if n.endswith(s) and len(n) > len(s) + 2:
            n = n[: -len(s)]
    return n


def bn_of(s):
    """Bengali genitive: কলকাতা -> কলকাতার, সল্টলেক -> সল্টলেকের."""
    return s + ("র" if s[-1] in "ািীুূৃেৈোৌ" else "ের")


def bn_hours(h):
    """3.5 -> 'সাড়ে তিন', 2.5 -> 'আড়াই', 1.5 -> 'দেড়', 4 -> 'চার'."""
    whole, frac = int(h), h - int(h)
    if 0.25 <= frac < 0.75:
        return {1: "দেড়", 2: "আড়াই"}.get(whole) or f"সাড়ে {BN_WORD.get(whole, str(whole).translate(BN_NUM))}"
    whole = round(h)
    return BN_WORD.get(whole, str(whole).translate(BN_NUM))


def script(pl):
    """The five voiceover lines, one per beat: [(bengali, english gloss), ...]. Facts from the guide only."""
    n, order, st = len(pl["order"]), pl["order"], pl["station"]
    zid = pl.get("key")
    area_bn = AREA_BN.get(zid) or pl.get("title_bn") or pl["area"]
    nbn = str(n).translate(BN_NUM)
    lines = [(f"এক রাতে {nbn}টা পুজো। {bn_of(area_bn)} মাস্টার রুট।", f"{n} pujos in one night. The {pl['area']} master route.")]
    if st:
        sbn = STATION_BN.get(st.get("id")) or st["name"].replace(" Sutanuti", "").replace(" (Suburban)", "")
        if st.get("line") in LINE_RGB:
            lines.append((f"{sbn} মেট্রোয় নেমে পড়ুন, তারপর শুধু লাল লাইনটা ধরে হাঁটুন।",
                          f"Get off at {station_name(st)}, then just follow the red line."))
        else:
            lines.append((f"{sbn} স্টেশনে নেমে পড়ুন, তারপর শুধু লাল লাইনটা ধরে হাঁটুন।",
                          f"Get off at {station_name(st)}, then just follow the red line."))
    else:
        lines.append(("শুধু লাল লাইনটা ধরে হাঁটুন।", "Just follow the red line."))
    mid = [order[i] for i in pl["lit"] if 0 < i < n - 1][:3]
    first, last = order[0], order[-1]
    if mid:
        mids_bn = ", ".join(bn_name(p) for p in mid[:-1]) + (" আর " if len(mid) > 1 else "") + bn_name(mid[-1])
        mids_en = ", ".join(short_name(p) for p in mid[:-1]) + (" and " if len(mid) > 1 else "") + short_name(mid[-1])
        lines.append((f"শুরু {bn_name(first)} দিয়ে। পথে {mids_bn}। শেষ স্টপ {bn_name(last)}।",
                      f"Start at {short_name(first)}. On the way, {mids_en}. Last stop, {short_name(last)}."))
    else:
        lines.append((f"শুরু {bn_name(first)} দিয়ে, শেষে {bn_name(last)}।", f"Start at {short_name(first)}, finish at {short_name(last)}."))
    km = round(pl["walk_m"] / 1000)
    lines.append((f"সব মিলিয়ে প্রায় {str(km).translate(BN_NUM)} কিলোমিটার, {bn_hours(pl['walk_min'] / 60)} ঘণ্টার হাঁটা।",
                  f"About {km} km in all, {round(pl['walk_min'] / 60, 1):g} hours of walking."))
    nxt = pl.get("next")
    nxt_bn = AREA_BN.get(pl.get("next_key")) if pl.get("next_key") else None
    tail = f" পরের পার্টে {nxt_bn}।" if nxt_bn else ""
    lines.append((f"রুটটা সেভ করে রাখুন।{tail} কমেন্টে ‘পুজো’ লিখুন, সব রুট পাঠিয়ে দেব।",
                  "Save this route." + (f" Next part: {nxt}." if nxt else "") + " Comment PUJO and we'll send you every route."))
    return lines


def vo_files(zone_id):
    """The recorded lines for a zone, 1..5, as paths (missing lines are None); [] when nothing is recorded."""
    d = VO_DIR / (zone_id or "")
    if not zone_id or not d.is_dir():
        return []
    out = [next((d / f"{k}{e}" for e in AUDIO_EXT if (d / f"{k}{e}").exists()), None) for k in range(1, 6)]
    return out if any(out) else []


def clean(p):
    """A recorded line with the silence trimmed off both ends and the loudness evened out (cached as WAV), so a
    phone recording or a WhatsApp voice note drops straight in."""
    import hashlib
    src = Path(p)
    dest = CACHE / "vo" / (hashlib.sha1(f"{src.resolve()}:{src.stat().st_mtime}".encode()).hexdigest()[:16] + ".wav")
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        trim = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af",
                        f"{trim},areverse,{trim},areverse,loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "1", str(dest)],
                       check=True)
    return dest


def duration(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


# ---- the plan -----------------------------------------------------------------------------------------------------

def catmull(a, b, c, d, n, tau=0.22):
    """n points of a gentle curve from b to c (a and d steer it; tau below the usual 0.5 keeps it from swinging
    wide of the stops)."""
    m1 = ((c[0] - a[0]) * tau, (c[1] - a[1]) * tau)
    m2 = ((d[0] - b[0]) * tau, (d[1] - b[1]) * tau)
    out = []
    for k in range(n):
        u = k / n
        h00, h10, h01, h11 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u, -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
        out.append(tuple(h00 * b[i] + h10 * m1[i] + h01 * c[i] + h11 * m2[i] for i in (0, 1)))
    return out


def plan(zone_id=None, g=None, ids=None, title=None, title_bn=None, area=None, part=None, nxt=None, ordered=False,
         max_lit=5, vo=None, next_key=None):
    """Everything the frames need. vo: the recorded lines' lengths in seconds (5 numbers, 0 for a missing line)."""
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
    # the route as a smooth line through every stop: one list of points per leg
    ext = [xy[0]] + list(xy) + [xy[-1]]
    legs = [catmull(ext[i], ext[i + 1], ext[i + 2], ext[i + 3], max(4, int(math.dist(xy[i], xy[i + 1]) // 6))) + [xy[i + 1]]
            for i in range(len(xy) - 1)]
    curve = [xy[0]] + [q for leg in legs for q in leg[1:]]
    # the lit medallions: the best-known stops with a photo, kept apart so none covers another
    cands = sorted((i for i, p in enumerate(order) if photo_of(p)), key=lambda i: (-(order[i].get("tier") or 0), i))
    lit = []
    for i in cands:
        if all(math.dist(xy[off + i], xy[off + j]) > 230 for j in lit) and len(lit) < max_lit:
            lit.append(i)
    lens = [sum(math.dist(a, b) for a, b in zip(leg, leg[1:])) for leg in legs]
    km, tot = [0.0], sum(lens) or 1
    for ln in lens:
        km.append(km[-1] + ln / tot * rt["walk_m"] / 1000)
    # the beats; with a recorded voiceover each lasts as long as its line
    v = list(vo or []) + [0.0] * 5
    t_dim = max(1.8, 0.15 + v[0] + 0.35)
    t_draw = t_dim + 0.7
    vo3_at = t_dim + (v[1] + 0.2 if v[1] else 0)
    draw = max(min(0.9, max(0.5, 10.0 / max(1, len(order)))) * len(order), (vo3_at + v[2] + 0.4) - t_draw)
    t_hold = t_draw + draw
    t_end = t_hold + max(2.8, 0.9 + v[3] + 0.5)
    end_secs = max(3.2, 0.25 + v[4] + 0.6)
    cues = [0.15, t_dim, vo3_at, t_hold + 0.9, t_end + 0.25]
    return {**rt, "xy": xy, "off": off, "legs": legs, "curve": curve, "lit": sorted(lit), "km": km, "to_px": to_px,
            "from_px": from_px, "area": area or rt["area"], "part": part, "next": nxt, "next_key": next_key,
            "per": draw / max(1, len(order)), "t_dim": t_dim, "t_draw": t_draw, "t_hold": t_hold, "t_end": t_end,
            "end_secs": end_secs, "cues": cues}


def path_to(pl, prog):
    """The smooth route from the Metro up to prog stops reached (fractional), and the point at its head."""
    legs, off = pl["legs"], pl["off"]
    reached = min(float(len(pl["order"])), max(0.0, prog))
    full, frac = int(reached), reached - int(reached)
    nlegs = full + off - 1  # whole legs walked (the first leg runs from the Metro to stop 1)
    path = [pl["xy"][0]]
    for leg in legs[:max(0, nlegs)]:
        path += leg[1:]
    if 0 <= nlegs < len(legs) and frac > 0:
        leg = legs[nlegs]
        u = ease(frac) * (len(leg) - 1)
        k = int(u)
        path += leg[1:k + 1]
        a, b = leg[k], leg[min(k + 1, len(leg) - 1)]
        path.append((a[0] + (b[0] - a[0]) * (u - k), a[1] + (b[1] - a[1]) * (u - k)))
    return path, path[-1]


def camera(pl, t):
    """(x0, y0, zoom): the map point at the frame's top-left and the zoom. Full view on the cover and the hold; in
    between it zooms in on the walker and follows him."""
    zin = ease((t - (pl["t_dim"] + 0.1)) / 0.9)
    zout = ease((t - pl["t_hold"]) / 0.9)
    f = zin * (1 - zout)
    if f <= 0:
        return 0.0, 0.0, 1.0
    if t < pl["t_draw"]:
        head = pl["xy"][0]
    else:  # the head, averaged over the last third of a second so the camera glides
        hs = [path_to(pl, (tt - pl["t_draw"]) / pl["per"])[1] for tt in (t - 0.33, t - 0.22, t - 0.11, t)]
        head = (sum(h[0] for h in hs) / 4, sum(h[1] for h in hs) / 4)
    z = 1 + (ZOOM - 1) * f
    sx, sy = head[0] + (ANCHOR[0] - head[0]) * f, head[1] + (ANCHOR[1] - head[1]) * f  # where the head sits on screen
    x0, y0 = head[0] - sx / z, head[1] - sy / z
    return min(max(x0, 0.0), W - W / z), min(max(y0, 0.0), H - H / z), z


# ---- drawing ------------------------------------------------------------------------------------------------------

def comp(im, layer, pos=(0, 0)):
    """Blend an RGBA layer onto the RGB frame."""
    im.paste(layer, (int(round(pos[0])), int(round(pos[1]))), layer)


def glow(size, draw_fn, blur=14, scale=4):
    """A soft glow layer: draw_fn(ImageDraw, k) draws at 1/scale size (k = 1/scale), blurred and scaled back up."""
    small = Image.new("RGBA", (size[0] // scale, size[1] // scale), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(small, "RGBA"), 1 / scale)
    return small.filter(ImageFilter.GaussianBlur(blur / scale)).resize(size, Image.BILINEAR)


def neon(im, path, a=1.0, width=7):
    """The route as a red neon tube: a wide blurred halo, the tube, a pale core."""
    if len(path) < 2:
        return
    comp(im, glow(im.size, lambda d, k: d.line([(x * k, y * k) for x, y in path], fill=RED + (int(200 * a),),
                                                width=max(2, int(34 * k)), joint="curve"), blur=18))
    d = ImageDraw.Draw(im, "RGBA")
    d.line(path, fill=RED + (int(255 * a),), width=width, joint="curve")
    d.line(path, fill=RED_HI + (int(230 * a),), width=2, joint="curve")


_SPRITE = {}


def sprite(kind, a):
    """Small glow sprites, cached per brightness: 'lamp' (120x120 gold) and 'spark' (40x40 warm white)."""
    key = (kind, round(a, 1))
    if key not in _SPRITE:
        if kind == "lamp":
            sp = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
            ImageDraw.Draw(sp).ellipse((30, 22, 90, 76), fill=GOLD + (int(150 * key[1]),))
            _SPRITE[key] = sp.filter(ImageFilter.GaussianBlur(14))
        else:
            sp = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
            ImageDraw.Draw(sp).ellipse((14, 14, 26, 26), fill=(255, 226, 170, int(255 * key[1])))
            _SPRITE[key] = sp.filter(ImageFilter.GaussianBlur(4))
    return _SPRITE[key]


def lamp(im, q, n=None, a=1.0, s=1.0):
    """A small lit pandal for the stops without a medallion: gold, glowing, red roof; the stop number once reached."""
    x, y = q
    comp(im, sprite("lamp", a), (x - 60, y - 70))
    d = ImageDraw.Draw(im, "RGBA")
    A = int(255 * a)
    d.polygon([(x - 17 * s, y - 14 * s), (x, y - 33 * s), (x + 17 * s, y - 14 * s)], fill=(214, 40, 40, A))
    d.rectangle((x - 12 * s, y - 14 * s, x + 12 * s, y + 2 * s), fill=GOLD + (A,))
    d.rounded_rectangle((x - 4 * s, y - 9 * s, x + 4 * s, y + 2 * s), 3, fill=(60, 20, 10, A))
    if n is not None:
        d.ellipse((x + 6, y - 46, x + 34, y - 18), fill=(20, 12, 10, A), outline=WHITE + (A,), width=2)
        d.text((x + 20, y - 32), str(n), font=F("bold", 17 if n < 10 else 15), fill=WHITE + (A,), anchor="mm")


def ripple(d, q, u):
    """A ring that spreads from a stop as the walk reaches it (u from 0 to 1)."""
    if 0 <= u <= 1:
        r = 14 + 70 * ease(u)
        d.ellipse((q[0] - r, q[1] - r, q[0] + r, q[1] + r), outline=GOLD + (int(220 * (1 - u)),), width=4)


def arch(dd, x0, y0, ww, hh, fill):
    dd.rectangle((x0, y0 + ww // 2, x0 + ww, y0 + hh), fill=fill)
    dd.ellipse((x0, y0, x0 + ww, y0 + ww), fill=fill)


def medallion(p, w=128, h=150):
    """The pandal's photo in an arched gold frame with a soft glow: an RGBA image (PAD of glow around the frame)."""
    src = crop(photo(p), w, h)
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
    other medallions and labels. Returns the frame's (x0, y0, x1, y1), its name included."""
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
    d.ellipse((x - 20 * s, y - 5 * s, x + 20 * s, y + 5 * s), fill=(0, 0, 0, 120))  # his shadow on the street
    for p_ in (leg(sw), leg(-sw)):
        d.line([hip, p_], fill=WHITE, width=int(8 * s))
    d.rounded_rectangle((sh[0] - 17 * s, sh[1] - 4 * s, sh[0] - 4 * s, sh[1] + 20 * s), int(4 * s), fill=(214, 40, 40))
    d.line([hip, sh], fill=WHITE, width=int(11 * s))
    for p_ in (arm(-sw), arm(sw)):
        d.line([sh, p_], fill=WHITE, width=int(6 * s))
    d.ellipse((sh[0] - 9 * s, sh[1] - 26 * s, sh[0] + 9 * s, sh[1] - 8 * s), fill=WHITE)


def header_layer(pl, art=None):
    """The night sky with the headline, as an RGBA layer over the map; art (a pujo photo) fades in on the right."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for y in range(720):  # opaque sky over the headline, fading into the map
        a = 255 if y < 600 else int(255 * (720 - y) / 120)
        d.line((0, y, W, y), fill=BG + (a,))
    if art is not None:  # a warm festival glow behind the right of the headline, tinted by the area's best photo
        warm = art.resize((1, 1), Image.LANCZOS).getpixel((0, 0))
        tint = tuple(int(0.55 * c + 0.45 * r) for c, r in zip(warm, (230, 40, 30)))
    else:
        tint = (200, 36, 30)
    g = Image.new("RGBA", (W // 4, 200), (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse((130, -60, 330, 150), fill=tint + (120,))
    ImageDraw.Draw(g).ellipse((-90, 60, 60, 190), fill=(255, 170, 60, 50))
    lay.alpha_composite(g.filter(ImageFilter.GaussianBlur(26)).resize((W, 800), Image.BILINEAR))
    n = len(pl["order"])
    brand = "PUJO PARIKRAMA GUIDE"
    f = F("semi", 26)
    bw = d.textlength(brand, font=f)
    d.text((W // 2, 226), brand, font=f, fill=GOLD, anchor="mm")
    d.line((W // 2 - bw / 2 - 90, 226, W // 2 - bw / 2 - 20, 226), fill=GOLD + (150,), width=2)
    d.line((W // 2 + bw / 2 + 20, 226, W // 2 + bw / 2 + 90, 226), fill=GOLD + (150,), width=2)
    when = "সন্ধ্যায়" if "evening" in (pl.get("hook") or "").lower() else "রাতে"
    parts = [(f"{n}".translate(BN_NUM), RED), ("টা পুজো · ", WHITE), ("১", RED), (f" {when}", WHITE)]
    fb = F("bnb", 118)
    tw = sum(d.textlength(s, font=fb) for s, _ in parts)
    while tw > 920:
        fb = F("bnb", fb.size - 4)
        tw = sum(d.textlength(s, font=fb) for s, _ in parts)
    x = (W - tw) / 2
    for s, c in parts:
        d.text((x, 330), s, font=fb, fill=c, anchor="lm", stroke_width=3, stroke_fill=BG)
        x += d.textlength(s, font=fb)
    a, b = f"{pl['area']} ", "Master Route"
    fe = F("bold", 62)
    while d.textlength(a + b, font=fe) > 900:
        fe = F("bold", fe.size - 2)
    x = (W - d.textlength(a + b, font=fe)) / 2
    d.text((x, 444), a, font=fe, fill=WHITE, anchor="lm", stroke_width=2, stroke_fill=BG)
    d.text((x + d.textlength(a, font=fe), 444), b, font=fe, fill=RED, anchor="lm", stroke_width=2, stroke_fill=BG)
    st = pl["station"]
    sub = f"{pl['walk_m'] / 1000:.1f} km on foot  ·  start at {station_name(st)}" if st else f"{pl['walk_m'] / 1000:.1f} km on foot"
    fs = fit(d, sub, "med", 30, 820)
    sw = d.textlength(sub, font=fs)
    d.text((W // 2, 518), sub, font=fs, fill=CREAM, anchor="mm", stroke_width=2, stroke_fill=BG)
    d.line((W // 2 - sw / 2 - 70, 518, W // 2 - sw / 2 - 18, 518), fill=MUTE + (150,), width=2)
    d.line((W // 2 + sw / 2 + 18, 518, W // 2 + sw / 2 + 70, 518), fill=MUTE + (150,), width=2)
    if pl.get("part"):
        tag = f"PART {pl['part']}"
        ft = F("bold", 24)
        tw = d.textlength(tag, font=ft)
        d.rounded_rectangle((W // 2 - tw / 2 - 18, 562, W // 2 + tw / 2 + 18, 600), 19, fill=RED + (235,))
        d.text((W // 2, 581), tag, font=ft, fill=WHITE, anchor="mm")
    return lay


def backdrop(pl):
    """The world: the dark street map at SS x the frame, faint neighbourhood names and the whole route dimmed, plus
    the same at frame size for the full view. Returns ((world, full), map credit)."""
    try:
        from . import basemap
        to2 = lambda la, lo: tuple(c * SS for c in pl["to_px"](la, lo))
        from2 = lambda x, y: pl["from_px"](x / SS, y / SS)
        world = basemap.draw((W * SS, H * SS), to2, from2, style=basemap.NIGHT, paper=basemap.NIGHT_PAPER)
        places, credit = world.info.get("places", []), basemap.ATTRIBUTION
    except Exception as e:  # no network or no tile reader: a plain dark field, so a batch never fails on the map
        print(f"basemap unavailable ({e}); drawing the plain night field", file=sys.stderr, flush=True)
        world, places, credit = Image.new("RGB", (W * SS, H * SS), BG), [], ""
    world = world.convert("RGB")
    d = ImageDraw.Draw(world, "RGBA")
    near = [(x * SS, y * SS) for x, y in pl["xy"]]
    seen = []
    for name, (x, y) in places:  # neighbourhood names, faint capitals, away from the stops
        if any(math.dist((x, y), q) < 120 * SS for q in near) or any(math.dist((x, y), q) < 160 * SS for q in seen):
            continue
        d.text((x, y), name.upper(), font=F("semi", 20 * SS), fill=(96, 104, 136, 120), anchor="mm")
        seen.append((x, y))
    curve2 = [(x * SS, y * SS) for x, y in pl["curve"]]  # the whole route, dim, under everything
    d.line(curve2, fill=(120, 26, 30, 255), width=5 * SS, joint="curve")
    full = world.resize((W, H), Image.LANCZOS)
    return (world, full), credit


def view(world_pair, cam):
    world, full = world_pair
    x0, y0, z = cam
    if z == 1.0 and x0 == 0 and y0 == 0:
        return full.copy()
    box = (x0 * SS, y0 * SS, (x0 + W / z) * SS, (y0 + H / z) * SS)
    return world.resize((W, H), Image.BILINEAR, box=box)


def overlay(pl):
    """What never moves on the map: the Metro label and the medallions (with their places), the header layer, the
    sparkles and the card photos. Returns (top, meds, credits)."""
    xy, off = pl["xy"], pl["off"]
    pts = [q for q in pl["curve"]]
    taken = [(x - 22, y - 40, x + 36, y + 12) for x, y in xy[off:]]  # the stop icons and their number badges
    st = pl["station"]
    if st:
        x, y = xy[0]
        name = station_name(st)
        f = F("bold", 22)
        tw = ImageDraw.Draw(Image.new("RGB", (8, 8))).textlength(name, font=f)
        cands = [(x - tw / 2, y + 32), (x - tw / 2, y - 60), (x + 34, y - 12), (x - 34 - tw, y - 12)]
        r = min(((min(max(cx, 40), 900 - tw), cy, min(max(cx, 40), 900 - tw) + tw, cy + 26) for cx, cy in cands),
                key=lambda r: sum(1 for px, py in pts if r[0] < px < r[2] and r[1] < py < r[3]) * 50 + sum(overlap(r, o) for o in taken))
        taken += [(x - 30, y - 30, x + 30, y + 30), r]
        pl["st_label"] = (name, f, (r[0] - x, r[1] - y))
    meds, credits, thumbs = [], [], {}
    art = None
    for i, p in enumerate(pl["order"]):  # every stop with a photo gets a thumbnail on its card
        if not photo_of(p):
            continue
        try:
            src = photo(p)
        except Exception as e:
            print(f"no photo for {p['id']} ({e})", file=sys.stderr, flush=True)
            continue
        thumbs[i] = crop(src, 88, 88)
        if i in pl["lit"]:
            m = medallion(p)
            fw, fh = m.width - 2 * PAD, m.height - 2 * PAD
            q = xy[off + i]
            r = place(q, (fw, fh), pts, taken)
            taken.append(r)
            meds.append((i, p, m, (r[0] - q[0], r[1] - q[1], r[2] - q[0], r[3] - q[1])))
            if art is None:
                art = src
        ph = photo_of(p)
        credits.append((ph[1], ph[2]))
    pl["thumbs"] = thumbs
    pl["walker_at"] = walker_spot(pl["curve"], [(q[0] + o[0], q[1] + o[1], q[0] + o[2], q[1] + o[3])
                                                for (i, _, _, o), q in ((m, xy[off + m[0]]) for m in meds)] + taken)
    rnd = random.Random(pl.get("key") or "route")
    pl["sparks"] = [(rnd.uniform(30, 1050), rnd.uniform(640, 1500), rnd.uniform(0, 6.3), rnd.uniform(1.2, 2.6)) for _ in range(34)]
    return header_layer(pl, art), meds, credits


def walker_spot(curve, boxes):
    """For the cover: the point on the route farthest from every medallion and label, where the walker stands."""
    best = None
    for p in curve[::3]:
        if not (FIT[0] < p[0] < FIT[2] and FIT[1] + 60 < p[1] < FIT[3]):
            continue
        me = (p[0] - 24, p[1] - 80, p[0] + 24, p[1] + 8)  # the figure stands on the line
        dd = min(max(r[0] - me[2], 0, me[0] - r[2]) + max(r[1] - me[3], 0, me[1] - r[3]) for r in boxes) if boxes else 999
        if best is None or dd > best[1]:
            best = (p, dd)
    return best[0] if best else curve[len(curve) // 2]


def card(im, title, sub, a=1.0, thumb=None, prog=None):
    """The stop card at the foot of the map, with the stop's photo when it has one and a bar counting the stops."""
    d = ImageDraw.Draw(im, "RGBA")
    y0, x0 = 1312, 70
    d.rounded_rectangle((x0, y0, 920, y0 + 120), 26, fill=(22, 14, 18, int(236 * a)), outline=RED + (int(180 * a),), width=2)
    tx = 104
    if thumb is not None and a > 0.5:
        m = Image.new("L", thumb.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, thumb.width - 1, thumb.height - 1), 18, fill=255)
        im.paste(thumb, (x0 + 18, y0 + 16), m)
        d.rounded_rectangle((x0 + 17, y0 + 15, x0 + 19 + thumb.width, y0 + 17 + thumb.height), 18, outline=GOLD, width=2)
        tx = x0 + 18 + thumb.width + 22
    d.text((tx, y0 + 20), title, font=fit(d, title, "bold", 40, 900 - tx), fill=WHITE + (int(255 * a),))
    d.text((tx, y0 + 72), sub, font=fit(d, sub, "med", 30, 900 - tx), fill=GOLD + (int(255 * a),))
    if prog is not None:  # a thin bar under the card: one dot per stop, red as far as the walk has come
        n, k = prog
        bx0, bx1, by = 104, 886, y0 + 140
        d.line((bx0, by, bx1, by), fill=(80, 70, 80, int(200 * a)), width=4)
        d.line((bx0, by, bx0 + (bx1 - bx0) * min(1.0, k / n), by), fill=RED + (int(255 * a),), width=4)
        for j in range(n):
            x = bx0 + (bx1 - bx0) * (j + 1) / n
            on = j < int(k + 0.12)
            d.ellipse((x - 5, by - 5, x + 5, by + 5), fill=(RED if on else (80, 70, 80)) + (int(255 * a),))


def frame(base, top, meds, pl, t):
    """One frame at t seconds (before the end card). base is backdrop()'s world pair, top the header layer."""
    xy, off, order = pl["xy"], pl["off"], pl["order"]
    n = len(order)
    cam = camera(pl, t)
    x0, y0, z = cam
    S = lambda q: ((q[0] - x0) * z, (q[1] - y0) * z)
    im = view(base, cam)
    cover = t < pl["t_dim"]
    drawing = t >= pl["t_draw"]
    prog = n if cover or t >= pl["t_hold"] else ((t - pl["t_draw"]) / pl["per"] if drawing else 0.0)
    if cover:  # the cover: the whole walk lit
        neon(im, [S(q) for q in pl["curve"]], a=1.0)
        head = None
    else:
        fade = 1.0 - ease((t - pl["t_dim"]) / 0.5)  # the lit cover route fades to the dim one under it
        if fade > 0:
            neon(im, [S(q) for q in pl["curve"]], a=fade)
        path, head = path_to(pl, prog) if drawing else ([xy[0]], xy[0])
        neon(im, [S(q) for q in path], a=1.0)
    d = ImageDraw.Draw(im, "RGBA")
    for sx, sy, ph, sp in pl.get("sparks", []):  # festival lights drifting over the map
        a = 0.25 + 0.35 * (0.5 + 0.5 * math.sin(ph + t * sp))
        comp(im, sprite("spark", a), (sx - 20, sy - 20 - (t * 6) % 30))
    d = ImageDraw.Draw(im, "RGBA")
    lit = {m[0] for m in meds}
    for i in range(n):
        q = S(xy[off + i])
        reached = cover or prog >= i + 1 - 0.12
        if drawing and not cover:
            ripple(d, q, (prog - (i + 1)) * pl["per"] / 0.6)
        if i in lit:
            r = 10 if reached else 8
            d.ellipse((q[0] - r, q[1] - r, q[0] + r, q[1] + r), fill=(255, 250, 244, 255 if reached else 190), outline=RED, width=4)
            continue
        pop = 1.0 + 0.35 * max(0.0, 1 - abs((prog - (i + 1)) * pl["per"] / 0.25)) if drawing and not cover else 1.0
        lamp(im, q, i + 1 if (reached and drawing and not cover) else None, a=1.0 if reached else 0.55, s=pop)
        d = ImageDraw.Draw(im, "RGBA")
    if pl["station"]:
        q = S(xy[0])
        c = LINE_RGB.get(pl["station"].get("line"), (104, 116, 140))  # a suburban rail start is grey with an R
        comp(im, sprite("lamp", 0.8), (q[0] - 60, q[1] - 50))
        d = ImageDraw.Draw(im, "RGBA")
        d.rounded_rectangle((q[0] - 26, q[1] - 26, q[0] + 26, q[1] + 26), 11, fill=c, outline=WHITE, width=3)
        d.text((q[0], q[1] + 2), "M" if pl["station"].get("line") in LINE_RGB else "R", font=F("bold", 30), fill=WHITE, anchor="mm")
        if pl.get("st_label"):
            name, f, (dx, dy) = pl["st_label"]
            d.text((q[0] + dx, q[1] + dy), name, font=f, fill=(150, 196, 255), stroke_width=4, stroke_fill=BG)
    for i, p, m, o in meds:  # the medallions keep their size and their place beside the stop as the camera moves
        q = S(xy[off + i])
        r = (q[0] + o[0], q[1] + o[1], q[0] + o[2], q[1] + o[3])
        if r[2] < -40 or r[0] > W + 40 or r[3] < 640 or r[1] > 1260:  # off screen, or down behind the card
            continue
        fh = m.height - 2 * PAD
        fx = min(max(q[0], r[0] + 20), r[2] - 20)
        fy = r[1] + fh if q[1] > r[1] + fh else r[1] + 40 if q[1] < r[1] else q[1]
        d.line([q, (fx, fy)], fill=GOLD + (230,), width=3)
        k = 1.0 + 0.14 * max(0.0, 1 - abs((prog - (i + 1)) * pl["per"] / 0.35)) if drawing and not cover else 1.0
        mm = m if k == 1.0 else m.resize((int(m.width * k), int(m.height * k)), Image.BILINEAR)
        cx, cy = (r[0] + r[2]) / 2, r[1] + fh / 2
        comp(im, mm, (cx - mm.width / 2, cy - mm.height / 2))
        d = ImageDraw.Draw(im, "RGBA")
        name = short_name(p)
        f = fit(d, name, "bold", 24, (r[2] - r[0]) + 50, minsize=16)
        d.text(((r[0] + r[2]) / 2, r[3] - 18), name, font=f, fill=WHITE, anchor="mm", stroke_width=4, stroke_fill=BG)
    if cover:  # on the cover the walker strolls the emptiest stretch of the route
        walker(d, (pl["walker_at"][0], pl["walker_at"][1] + 8), phase=0.9, s=1.15)
    elif head is not None:
        walker(d, S((head[0], head[1] + 6 / z)), phase=t * 9, s=1.0 + 0.15 * (z - 1))
    comp(im, top)
    st = pl["station"]
    st_name = station_name(st) if st else ""
    if pl["t_dim"] <= t < pl["t_draw"] + 0.3 and st:
        card(im, f"Start: {st_name}", "Get off here and follow the red line", ease((t - pl["t_dim"]) / 0.4))
    elif pl["t_draw"] + 0.3 <= t < pl["t_hold"]:
        k = min(n, max(1, int(prog + 0.12)))
        card(im, f"{k} · {order[k - 1]['name']}", f"{pl['km'][off + k - 1]:.1f} km walked  ·  stop {k} of {n}",
             thumb=pl.get("thumbs", {}).get(k - 1), prog=(n, prog))
    elif t >= pl["t_hold"]:
        card(im, f"~{round(pl['steps'], -2):,} steps  ·  ~{round(pl['walk_min'] / 60, 1):g} h walking",
             f"Best for: {pl['best']}" if pl["best"] else f"Start at {st_name}", prog=(n, n))
    return im


def end_frame(pl, t, credits, map_credit, under=None):
    """The end card, over the last map frame blurred into the night (under), or plain night."""
    if under is not None:
        im = under.filter(ImageFilter.GaussianBlur(14))
        im = Image.blend(im, Image.new("RGB", (W, H), BG), 0.72)
    else:
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
        fw = d.textlength(nx, font=F("bold", 36))
        d.rounded_rectangle((cx - fw / 2 - 26, y - 34, cx + fw / 2 + 26, y + 34), 34, fill=RED + (int(a * 0.92),))
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
           ordered=False, next_key=None, vo=None):
    """Writes the reel to out. vo: the recorded lines (paths, 1..5); by default marketing/vo/night/<zone>/."""
    g = g or json.loads((ROOT / "app" / "data" / "guide.json").read_text(encoding="utf-8"))
    vo = vo_files(zone_id) if vo is None else vo
    vo = [clean(p) if p else None for p in vo]
    lens = [duration(p) if p else 0.0 for p in vo] if vo else None
    pl = plan(zone_id, g, ids, title, title_bn, area, part, nxt, ordered, vo=lens, next_key=next_key)
    pl["hook"] = hook
    base, map_credit = backdrop(pl)
    top, meds, credits = overlay(pl)
    total = pl["t_end"] + pl["end_secs"]
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-ss", "2", "-i", str(AUDIO)]
    lines = [(p, c) for p, c in zip(vo or [], pl["cues"]) if p]
    for p, _ in lines:
        cmd += ["-i", str(p)]
    bed = 0.32 if lines else 0.9  # the dhak drops under the voice
    fx = [f"[1:a]atrim=0:{total:.2f},afade=t=in:d=0.3,afade=t=out:st={total - 1.2:.2f}:d=1.2,volume={bed}[bed]"]
    for k, (p, c) in enumerate(lines):
        ms = int(c * 1000)
        fx.append(f"[{k + 2}:a]aresample=48000,adelay={ms}|{ms},volume=1.2[v{k}]")
    mix = "[bed]" + "".join(f"[v{k}]" for k in range(len(lines)))
    fx.append(f"{mix}amix=inputs={len(lines) + 1}:normalize=0:duration=first[a]")
    cmd += ["-filter_complex", ";".join(fx), "-map", "0:v", "-map", "[a]", "-t", f"{total:.2f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-c:a", "aac", "-b:a", "160k", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    ends, cover, last = {}, None, None
    for f in range(int(total * FPS)):
        t = f / FPS
        if t < pl["t_dim"]:
            cover = cover or frame(base, top, meds, pl, 0.0)  # the cover holds still, so it renders once
            im = cover
        elif t < pl["t_end"]:
            im = last = frame(base, top, meds, pl, t)
        else:
            k = min(f - int(pl["t_end"] * FPS), 12)
            if k not in ends:
                ends[k] = end_frame(pl, k / FPS, credits, map_credit, under=last)
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
    ap.add_argument("--next-zone", help="the next part's zone id (for the voiceover's Bengali name)")
    ap.add_argument("--ordered", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--still", type=float, help="write one frame at this time (s) as a JPEG instead of the video")
    ap.add_argument("--script", action="store_true", help="print the voiceover script")
    a = ap.parse_args(argv)
    ids = [i.strip() for i in a.ids.split(",") if i.strip()] if a.ids else None
    if not (a.zone or ids):
        ap.error("--zone or --ids")
    if a.script:
        pl = plan(a.zone, None, ids, a.title, a.title_bn, a.area, a.part, a.next, a.ordered, next_key=a.next_zone)
        for k, (bn, en) in enumerate(script(pl), 1):
            print(f"{k}. {bn}\n   ({en})")
        return
    if not a.out:
        ap.error("--out")
    if a.still is not None:
        pl = plan(a.zone, None, ids, a.title, a.title_bn, a.area, a.part, a.next, a.ordered, next_key=a.next_zone)
        base, map_credit = backdrop(pl)
        top, meds, credits = overlay(pl)
        if a.still < pl["t_end"]:
            im = frame(base, top, meds, pl, a.still)
        else:
            im = end_frame(pl, a.still - pl["t_end"], credits, map_credit, under=frame(base, top, meds, pl, pl["t_end"] - 0.05))
        im.save(a.out, quality=90)
        return
    secs, pl = render(a.zone, a.out, ids=ids, title=a.title, title_bn=a.title_bn, area=a.area, part=a.part, nxt=a.next,
                      ordered=a.ordered, next_key=a.next_zone)
    print(f"{a.out}: {secs}s, {len(pl['order'])} stops")


if __name__ == "__main__":
    main()
