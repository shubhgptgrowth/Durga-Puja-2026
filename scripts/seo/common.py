"""Shared helpers for the crawlable pages: escaping, dates, times, money, JSON-LD."""
import html
import json
import re
from datetime import date

NAME = "Pujo Parikrama"

TAGS = {
    "heritage": "heritage puja", "state-art": "state-of-the-art pandal", "neighbourhood": "neighbourhood puja",
    "artisan": "artisan work", "lake": "lakeside setting", "blockbuster": "blockbuster crowd-puller", "bonedi": "bonedi bari (aristocratic family) puja",
    "traditional": "traditional idol", "lights": "light work", "theme": "theme pandal", "grand": "grand scale", "eco": "eco-friendly theme",
    "art": "art installation", "replica": "replica pandal", "fair": "puja fair (mela)", "adda": "adda spot",
}
FOOD_TYPE = {"street": "street food stall", "sweets": "sweet shop", "drinks": "drinks and snacks stop", "cabin": "old Kolkata cabin", "restaurant": "restaurant"}
FOR_TWO = {"street": [150, 250, 400], "sweets": [150, 300, 500], "drinks": [120, 250, 400], "cabin": [300, 500, 800], "restaurant": [500, 1000, 1800]}
LINE = {"blue": "Blue Line", "green": "Green Line (East–West Metro)", "purple": "Purple Line", "orange": "Orange Line"}
CAR = {"avoid": "Avoid driving: the lanes are closed to cars most evenings.", "limited": "Driving is possible but parking is scarce; come by metro if you can.", "ok": "Driving is manageable; use the parking listed below."}
CROWD = [(85, "extremely crowded"), (65, "very crowded"), (45, "busy"), (25, "moderate"), (0, "quiet")]
MAIN_DAYS = ["panchami", "shashthi", "saptami", "ashtami", "navami", "dashami"]


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def ampm(h):
    h = int(h) % 24
    return "12 am" if h == 0 else "12 pm" if h == 12 else f"{h} am" if h < 12 else f"{h - 12} pm"


def hrange(hours):
    """[5, 6] -> '5–7 am'; [23, 0] -> '11 pm–1 am'; separate runs joined with commas."""
    hs, runs = list(hours), []
    for h in hs:
        if runs and (runs[-1][1] + 1) % 24 == h:
            runs[-1][1] = h
        else:
            runs.append([h, h])
    out = []
    for a, b in runs:
        x, y = ampm(a), ampm(b + 1)
        out.append(f"{x.split()[0]}–{y}" if x.split()[1] == y.split()[1] else f"{x}–{y}")
    return ", ".join(out)


def clock(t):
    h, m = map(int, t.split(":"))
    s = ampm(h)
    return s if m == 0 else s.replace(" ", f":{m:02d} ")


def crowd_word(c):
    return next(w for lim, w in CROWD if c >= lim)


def nice_date(d, year=False):
    x = date.fromisoformat(d)
    return f"{x.day} {x.strftime('%B')}" + (f" {x.year}" if year else "") + f" ({x.strftime('%A')})"


def cost2(f):
    return f.get("cost2") or (FOR_TWO.get(f["type"]) or FOR_TWO["restaurant"])[min(max(f.get("price") or 2, 1), 3) - 1]


def rupees(n):
    s = str(int(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        s = head + "," + tail
    return "₹" + s


def km(m):
    return f"{m / 1000:.1f} km" if m >= 1000 else f"{int(m)} m"


def jsonld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>"
