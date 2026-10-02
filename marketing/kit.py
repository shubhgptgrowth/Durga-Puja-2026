"""Daily Instagram + WhatsApp content kit for the Durga Puja 2026 push (docs/MARKETING.md).

    python -m marketing.kit --out app/kit [--today 2026-10-11] [--stats place_stats.json]

Writes, for every campaign day (3 Oct → 22 Oct):
  app/kit/<date>/assets.json   cards to render (post 1080×1350, story 1080×1920) + captions (EN/BN)
  app/kit/assets.json          every day's cards, for marketing/render.mjs
  app/kit/index.html           the team's daily page: preview, download, copy caption, open in WhatsApp
Then `node marketing/render.mjs app/kit` turns the cards into PNGs and builds the QR posters.

Everything is derived from app/data/guide.json, so the kit never disagrees with the app. On puja days,
a place_stats snapshot (--stats) turns "quiet hours" cards into live "trending now" cards for today.
Stdlib only.
"""
import argparse
import datetime as dt
import html
import json
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://shubhgptgrowth.github.io/Durga-Puja-2026/"
START, END = dt.date(2026, 10, 3), dt.date(2026, 10, 22)
TAGS = "#DurgaPuja2026 #KolkataDurgaPuja #DurgaPujo #PandalHopping #Kolkata #PujoParikrama #দুর্গাপুজো #পুজো"
REGION_TAG = {"north": "#NorthKolkata", "central": "#CentralKolkata", "south": "#SouthKolkata", "east": "#SaltLake #NewTown", "howrah": "#Howrah"}

# Day-by-day plan. Before Shashthi: build intent (areas, food, getting there, trails). Puja days: live utility.
SCHEDULE = {
    "2026-10-03": ("launch", {}),
    "2026-10-04": ("region", {"region": "north"}),
    "2026-10-05": ("region", {"region": "south"}),
    "2026-10-06": ("region", {"region": "central"}),
    "2026-10-07": ("region", {"region": "east"}),
    "2026-10-08": ("food", {}),
    "2026-10-09": ("getting_there", {}),
    "2026-10-10": ("mahalaya", {}),
    "2026-10-11": ("trail", {"trail": "south_classic"}),
    "2026-10-12": ("trail", {"trail": "north_heritage"}),
    "2026-10-13": ("trail", {"trail": "central_blockbusters"}),
    "2026-10-14": ("trail", {"trail": "behala_trail"}),
    "2026-10-15": ("trail", {"trail": "all_nighter"}),
    "2026-10-16": ("live", {"day": "panchami"}),
    "2026-10-17": ("live", {"day": "shashthi"}),
    "2026-10-18": ("live", {"day": "saptami"}),
    "2026-10-19": ("live", {"day": "ashtami"}),
    "2026-10-20": ("live", {"day": "navami"}),
    "2026-10-21": ("live", {"day": "dashami"}),
    "2026-10-22": ("recap", {}),
}


def link(src):
    return f"{SITE}?src={src}"


def hour_label(h):
    return f"{(h % 12) or 12} {'am' if h < 12 else 'pm'}"


def stars(n):
    return "★" * int(n)


class Kit:
    def __init__(self, g, stats=None, today=None):
        self.g = g
        self.stats = stats or {}
        self.today = today
        self.pandal = {p["id"]: p for p in g["pandals"]}
        self.food = {f["id"]: f for f in g["food"]}
        self.zone = {z["id"]: z for z in g["zones"]}
        self.region = {r["id"]: r for r in g["regions"]}
        self.days = {d["id"]: d for d in g["meta"]["days"]}
        self.trails = {i["id"]: i for i in g["itineraries"]}
        self.dish_photos = g.get("dish_photos", {})

    # ---------------------------------------------------------------- helpers
    def photo(self, pid):
        """First Commons photo of a pandal or eatery, with the credit the licence requires."""
        ph = (self.pandal.get(pid) or self.food.get(pid) or {}).get("photos") or []
        if not ph:
            return None
        p = ph[0]
        return {"src": p["src"], "credit": f"Photo: {p.get('author') or 'Wikimedia Commons'} · {p.get('license', '')} · Wikimedia Commons"}

    def region_pandals(self, rid, n=6):
        zs = set(self.region[rid]["zone_ids"])
        ps = [p for p in self.g["pandals"] if p["zone"] in zs]
        return sorted(ps, key=lambda p: (-p["popularity"], -len(p.get("photos") or []), p["name"]))[:n]

    def quiet(self, p, day):
        """The pandal's recommended slot (it differs per pandal); dawn is quiet everywhere, so say it once in the caption."""
        return p.get("best_slot_label") or " · ".join(hour_label(h) for h in (p["quiet_hours"].get(day) or [])[:2])

    def countdown(self, d):
        return (dt.date(2026, 10, 17) - d).days

    # ---------------------------------------------------------------- day builder
    def day(self, d):
        key = d.isoformat()
        theme, opt = SCHEDULE[key]
        cards, wa = getattr(self, "t_" + theme)(d, **opt)
        n = self.countdown(d)
        if n > 0:
            cards.append(self.card(d, "countdown", "story", "hero", {
                "kicker": "Durga Puja 2026 · Kolkata", "big": str(n), "title": f"{'day' if n == 1 else 'days'} to Shashthi",
                "subtitle": "Plan your pandal hopping by area. Quiet hours, food, parking and routes in one free app.",
                "subtitle_bn": "এলাকা ধরে ঠাকুর দেখার প্ল্যান। কখন ভিড় কম, কী খাবেন, কোথায় পার্কিং, কোন রুট। সব এক ফ্রি অ্যাপে।",
                "cta": "Link in story 👆", "photo": self.photo("kumartuli_park"),
            }, en=f"{n} days to go! Plan your pujo now 👉 link in bio.", bn=f"আর মাত্র {n} দিন! এখনই পুজোর প্ল্যান করুন 👉 বায়োতে লিংক।", src="ig_story"))
        elif theme == "live":
            cards.append(self.card(d, "mycard", "story", "hero", {
                "kicker": f"{self.days[opt['day']]['name']} · {self.days[opt['day']]['name_bn']}", "big": "📸", "title": "Share your My Pujo card",
                "subtitle": "Pandals visited, steps walked, badges unlocked. Me tab → Share my Pujo card. Tag us!",
                "subtitle_bn": "কটা প্যান্ডেল, কত পা হাঁটলেন, কটা ব্যাজ। Me ট্যাব → আমার পুজো কার্ড। আমাদের ট্যাগ করুন!",
                "cta": "Link in story 👆",
            }, en="How many pandals so far? Share your My Pujo card and tag us 🪔", bn="এখনও পর্যন্ত কটা ঠাকুর দেখলেন? আমার পুজো কার্ড শেয়ার করে আমাদের ট্যাগ করুন 🪔", src="ig_story"))
        return {"date": key, "theme": theme, "cards": cards, "whatsapp": wa}

    def card(self, d, slug, fmt, tpl, data, en, bn, src, tags=""):
        cid = f"{d.strftime('%m%d')}-{slug}-{fmt}"
        cap_en = f"{en}\n\n{TAGS} {tags}".strip()
        cap_bn = f"{bn}\n\n{TAGS} {tags}".strip()
        return {"id": cid, "date": d.isoformat(), "format": fmt, "template": tpl, "data": data,
                "caption_en": cap_en, "caption_bn": cap_bn, "link": link(src), "src": src,
                "file": f"{d.isoformat()}/{cid}.jpg"}

    def wa(self, d, en, bn):
        """WhatsApp: a Channel post and a forward-ready message for groups, each with its own tracked link."""
        return {"channel": f"{en}\n\n{bn}\n\n👉 {link('wa_channel')}",
                "forward": f"{en}\n\n👉 {link('wa_fwd')}\n\n{bn}\n\n_Forward to your pujo group 🙏_"}

    # ---------------------------------------------------------------- themes
    def t_launch(self, d):
        n = len(self.g["pandals"])
        cards = [self.card(d, "launch", "post", "hero", {
            "kicker": "Free · English & বাংলা · Works offline", "big": "🪔", "title": "Pujo Parikrama 2026",
            "subtitle": f"{n} pandals across North, Central, South, East and Howrah. Quiet hours, food, parking, metro, bus and auto routes, live check-ins and a step tracker.",
            "subtitle_bn": f"উত্তর, মধ্য, দক্ষিণ, পূর্ব আর হাওড়ার {n}টা প্যান্ডেল। কখন ভিড় কম, খাবার, পার্কিং, মেট্রো-বাস-অটো রুট, লাইভ চেক-ইন আর স্টেপ ট্র্যাকার।",
            "cta": "Link in bio", "photo": self.photo("tala_prattoy"),
        }, en=f"Your pandal-hopping planner for Durga Puja 2026 is here 🪔\n\n✅ {n} pandals, sorted by area\n✅ When each one is quietest\n✅ Where to eat and park\n✅ Metro, bus and shared-auto routes\n✅ Live check-ins: see where the crowd is\n\nFree, no sign-up. Link in bio.",
            bn=f"দুর্গাপুজো ২০২৬-এর ঠাকুর দেখার গাইড এসে গেছে 🪔\n\n✅ এলাকা ধরে {n}টা প্যান্ডেল\n✅ কোনটায় কখন ভিড় কম\n✅ কোথায় খাবেন, কোথায় গাড়ি রাখবেন\n✅ মেট্রো, বাস আর অটোর রুট\n✅ লাইভ চেক-ইন: কোথায় কত ভিড়\n\nফ্রি, সাইন-আপ লাগবে না। বায়োতে লিংক।", src="ig_bio")]
        wa = self.wa(d, f"🪔 Pujo Parikrama 2026: a free pandal-hopping guide for Kolkata. {n} pandals by area, quiet hours, food, parking, metro/bus/auto routes and live crowd check-ins.",
                     f"🪔 পুজো পরিক্রমা ২০২৬: কলকাতার ঠাকুর দেখার ফ্রি গাইড। এলাকা ধরে {n}টা প্যান্ডেল, কখন ভিড় কম, খাবার, পার্কিং, মেট্রো-বাস-অটো রুট আর লাইভ ভিড়ের খবর।")
        return cards, wa

    def t_region(self, d, region):
        r = self.region[region]
        ps = self.region_pandals(region)
        items = [{"name": p["name"], "name_bn": p.get("name_bn", ""), "meta": f"{stars(p['popularity'])} · 🚇 {p['nearest_metro']['name'].replace(' (Suburban)', '')} · {p['nearest_metro']['walk_min']} min"} for p in ps]
        areas = " · ".join(self.zone[z]["short"] for z in r["zone_ids"] if z in self.zone)
        npan = sum(1 for p in self.g["pandals"] if self.zone[p["zone"]]["region"] == region)
        data = {"kicker": f"{r['name']} Kolkata · {r['name_bn']}", "title": f"{r['name']}: must-see pandals", "subtitle": areas,
                "items": items, "foot": f"All {npan} {r['name']} pandals, with quiet hours and routes, are in the app.", "accent": r["color"], "photo": self.photo(ps[0]["id"])}
        top = "\n".join(f"{i + 1}. {p['name']}" for i, p in enumerate(ps))
        top_bn = "\n".join(f"{i + 1}. {p.get('name_bn') or p['name']}" for i, p in enumerate(ps))
        cards = [self.card(d, f"region-{region}", "post", "list", data,
                           en=f"{r['name']} Kolkata pandal guide 📍\n\n{top}\n\nSave this post, and open the app for quiet hours, nearest metro and the best walking order. Link in bio.",
                           bn=f"{r['name_bn']} কলকাতার প্যান্ডেল গাইড 📍\n\n{top_bn}\n\nপোস্টটা সেভ করে রাখুন। কখন ভিড় কম, কাছের মেট্রো আর হাঁটার সেরা রুট অ্যাপে। বায়োতে লিংক।",
                           src="ig_bio", tags=REGION_TAG.get(region, "")),
                 self.card(d, f"region-{region}", "story", "list", {**data, "items": items[:5], "cta": "Plan this area 👆"},
                           en=f"{r['name']} Kolkata: where to start?", bn=f"{r['name_bn']} কলকাতা: কোথা থেকে শুরু?", src="ig_story")]
        wa = self.wa(d, f"📍 {r['name']} Kolkata pandal guide:\n{top}", f"📍 {r['name_bn']} কলকাতার প্যান্ডেল:\n{top_bn}")
        return cards, wa

    def t_food(self, d):
        fs = sorted(self.g["food"], key=lambda f: (f["type"] == "street", -len(f["dishes"]), f["name"]))[:6]
        items = [{"name": f["name"].split(" (")[0], "meta": f"{', '.join(f['dishes'][:2])} · {self.zone[f['zone']]['short']}"} for f in fs]
        dish = next((x for f in fs for x in f["dishes"] if self.dish_photos.get(x)), None)
        photo = {"src": self.dish_photos[dish]["src"], "credit": f"Photo: {self.dish_photos[dish].get('author', '')} · {self.dish_photos[dish].get('license', '')} · Wikimedia Commons"} if dish else None
        data = {"kicker": "Pujo pet-pujo · পেটপুজো", "title": "Eat your way through the pujas", "subtitle": "Legendary cabins, sweets and rolls near the big pandals",
                "items": items, "foot": f"{len(self.g['food'])} food stops, mapped next to the pandals.", "accent": "#B45309", "photo": photo}
        lines = "\n".join(f"🍽 {i['name']}: {i['meta']}" for i in items)
        cards = [self.card(d, "food", "post", "list", data,
                           en=f"Pandal hopping runs on kabiraji and kathi rolls 🍢\n\n{lines}\n\nEvery stop is mapped next to the pandals. Link in bio.",
                           bn=f"ঠাকুর দেখা মানেই কবিরাজি আর রোল 🍢\n\n{lines}\n\nপ্যান্ডেলের পাশেই কোথায় খাবেন, অ্যাপে দেখে নিন। বায়োতে লিংক।", src="ig_bio", tags="#KolkataFood #FoodieKolkata"),
                 self.card(d, "food", "story", "list", {**data, "items": items[:5], "cta": "Find food near you 👆"},
                           en="Where to eat between pandals?", bn="ঠাকুর দেখার ফাঁকে কোথায় খাবেন?", src="ig_story")]
        wa = self.wa(d, f"🍢 Pujo food stops near the big pandals:\n{lines}", "🍢 বড় প্যান্ডেলগুলোর কাছে কোথায় খাবেন, অ্যাপে ম্যাপ করা আছে।")
        return cards, wa

    def t_getting_there(self, d):
        items = [
            {"name": "🚇 Metro first", "meta": "Every pandal shows its nearest station and the walk from it."},
            {"name": "🛺 Shared autos", "meta": "Common routes like Gariahat ↔ Jadavpur and Shyambazar ↔ Ultadanga."},
            {"name": "🚌 Buses", "meta": "Nearby stops and route numbers where they're mapped."},
            {"name": "🅿 Parking", "meta": "Park & ride at Noapara, Kavi Subhash and more. 'I parked here' saves your spot."},
            {"name": "🚫 No-car zones", "meta": "Each area says if cars are a bad idea in the evening."},
        ]
        data = {"kicker": "Getting there · কীভাবে যাবেন", "title": "Skip the jam: metro, auto and park & ride", "items": items,
                "foot": "Tap any pandal → Getting there.", "accent": "#1D4ED8"}
        cards = [self.card(d, "getting-there", "post", "list", data,
                           en="Don't spend Ashtami in a traffic jam 🚦\n\nOpen any pandal in the app to see the nearest metro, shared-auto routes, bus stops and parking, plus a one-tap transit route. Link in bio.",
                           bn="অষ্টমী যেন জ্যামে না কাটে 🚦\n\nঅ্যাপে যেকোনো প্যান্ডেল খুললেই কাছের মেট্রো, অটোর রুট, বাস স্টপ আর পার্কিং। বায়োতে লিংক।", src="ig_bio", tags="#KolkataMetro"),
                 self.card(d, "getting-there", "story", "list", {**data, "cta": "Plan your route 👆"},
                           en="Metro, auto or car?", bn="মেট্রো, অটো না গাড়ি?", src="ig_story")]
        wa = self.wa(d, "🚇 Before you go: every pandal in Pujo Parikrama shows the nearest metro, shared-auto routes, bus stops and parking.",
                     "🚇 যাওয়ার আগে দেখে নিন: প্রতিটা প্যান্ডেলের কাছের মেট্রো, অটোর রুট, বাস স্টপ আর পার্কিং।")
        return cards, wa

    def t_mahalaya(self, d):
        cards = [self.card(d, "mahalaya", "post", "hero", {
            "kicker": "শুভ মহালয়া · Subho Mahalaya", "big": "🙏", "title": "Ya Devi Sarvabhuteshu…",
            "subtitle": "Devi Paksha begins. Seven days to go. Plan your pujo: pandals by area, quiet hours, food and routes.",
            "subtitle_bn": "দেবীপক্ষের শুরু। আর সাত দিন। এলাকা ধরে প্যান্ডেল, কখন ভিড় কম, খাবার আর রুট। প্ল্যান শুরু করুন।",
            "cta": "Link in bio", "photo": self.photo("kumartuli_park")},
            en="Subho Mahalaya 🙏 Devi Paksha begins today. Start planning your pujo: which pandals, in what order, when they're quietest. Link in bio.",
            bn="শুভ মহালয়া 🙏 আজ থেকে দেবীপক্ষ। কোন প্যান্ডেল, কোন ক্রমে, কখন ভিড় কম: পুজোর প্ল্যান শুরু করুন। বায়োতে লিংক।", src="ig_bio", tags="#Mahalaya #মহালয়া")]
        wa = self.wa(d, "🙏 Subho Mahalaya! Seven days to Shashthi. Plan your pandal hopping, free:", "🙏 শুভ মহালয়া! ষষ্ঠী আর সাত দিন। ঠাকুর দেখার প্ল্যান করুন, ফ্রি:")
        return cards, wa

    def t_trail(self, d, trail):
        it = self.trails[trail]
        stops = [s["pandal"] for seg in it["segments"] for s in seg.get("stops", [])]
        items = [{"name": self.pandal[s]["name"], "meta": stars(self.pandal[s]["popularity"])} for s in stops[:7]]
        day = self.days[it["day"]]
        tt = it["totals"]
        data = {"kicker": f"Trail · {day['name']} from {it['start_time']}", "title": it["name"], "subtitle": it["blurb"], "items": items,
                "foot": f"{it['pandal_count']} pandals · {tt['walk_km']} km · ~{round(tt['duration_min'] / 60)} h · {tt['steps']:,} steps", "accent": "#9F1239",
                "photo": self.photo(stops[0])}
        cards = [self.card(d, f"trail-{trail}", "post", "list", data,
                           en=f"{it['name']} 🚶\n\n{it['blurb']}\n\n{it['pandal_count']} pandals, {tt['walk_km']} km, about {round(tt['duration_min'] / 60)} hours, starting {day['name']} at {it['start_time']}. Open the trail in the app for the stop-by-stop route and a live step count. Link in bio.",
                           bn=f"{it['name_bn']} 🚶\n\n{it['blurb_bn']}\n\n{it['pandal_count']}টা প্যান্ডেল, {tt['walk_km']} কিমি, মোটামুটি {round(tt['duration_min'] / 60)} ঘণ্টা। {day['name_bn']}তে {it['start_time']} থেকে। অ্যাপে পুরো রুট আর লাইভ স্টেপ কাউন্ট। বায়োতে লিংক।",
                           src="ig_bio", tags="#PujoTrail"),
                 self.card(d, f"trail-{trail}", "story", "list", {**data, "items": items[:5], "cta": "Start this trail 👆"},
                           en=f"Try the {it['name']}", bn=f"{it['name_bn']} ঘুরে আসুন", src="ig_story")]
        wa = self.wa(d, f"🚶 {it['name']}: {it['pandal_count']} pandals, {tt['walk_km']} km. {it['blurb']}", f"🚶 {it['name_bn']}: {it['pandal_count']}টা প্যান্ডেল, {tt['walk_km']} কিমি। {it['blurb_bn']}")
        return cards, wa

    def t_live(self, d, day):
        dd = self.days[day]
        live = d == self.today and self.stats
        if live:
            rows = sorted(((self.stats[p["id"]].get("today", 0), p) for p in self.g["pandals"] if p["id"] in self.stats), key=lambda x: -x[0])
            rows = [r for r in rows if r[0] > 0][:6]
        if live and len(rows) >= 3:
            items = [{"name": p["name"], "meta": f"🔥 {n:,} check-ins today · 🚇 {p['nearest_metro']['name']}"} for n, p in rows]
            title, sub = "Trending right now", "Live check-ins from people at the pandals"
            en = "🔥 Trending pandals right now, from live check-ins:\n\n" + "\n".join(f"{i + 1}. {p['name']} ({n:,})" for i, (n, p) in enumerate(rows))
            bn = "🔥 এই মুহূর্তে যেখানে সবচেয়ে বেশি লোক (লাইভ চেক-ইন):\n\n" + "\n".join(f"{i + 1}. {p.get('name_bn') or p['name']}" for i, (n, p) in enumerate(rows))
            slug = "trending"
        else:
            # Famous pandals, different ones each day, at most two per best-time slot so the advice varies.
            pool = sorted((p for p in self.g["pandals"] if p["popularity"] >= 4), key=lambda p: (-p["popularity"], p["id"]))
            k = list(self.days).index(day) * 5
            pool = pool[k % len(pool):] + pool[:k % len(pool)]
            top, per = [], {}
            for p in pool:
                if per.get(p["best_slot"], 0) < 2:
                    top.append(p); per[p["best_slot"]] = per.get(p["best_slot"], 0) + 1
                if len(top) == 6:
                    break
            items = [{"name": p["name"], "meta": f"🕰 Best {self.quiet(p, day)} · {self.zone[p['zone']]['short']}"} for p in top]
            title, sub = f"{dd['name']}: beat the crowd", "Best time for the big pandals · every pandal is calm 5–8 am"
            en = f"{dd['name']} crowd hack 🕰 Best time for the big ones today (and every pandal is calm from 5 to 8 am):\n\n" + "\n".join(f"• {p['name']}: {self.quiet(p, day)}" for p in top)
            bn = f"{dd['name_bn']}র ভিড় এড়ানোর উপায় 🕰 বড় প্যান্ডেলগুলোয় যাওয়ার সেরা সময় (আর ভোর ৫টা থেকে ৮টা সব জায়গাই ফাঁকা):\n\n" + "\n".join(f"• {p.get('name_bn') or p['name']}: {self.quiet(p, day)}" for p in top)
            slug = "quiet"
        data = {"kicker": f"{dd['name']} · {dd['name_bn']} · {d.strftime('%d %b')}", "title": title, "subtitle": sub, "items": items,
                "foot": "Live crowd, food and routes for every pandal in the app.", "accent": "#B91C1C"}
        cards = [self.card(d, slug, "post", "list", data, en=en + "\n\nCheck in when you get there so others see the crowd. Link in bio.",
                           bn=bn + "\n\nপৌঁছে চেক-ইন করুন, যাতে অন্যরাও ভিড়ের খবর পান। বায়োতে লিংক।", src="ig_bio", tags=f"#{dd['name']}"),
                 self.card(d, slug, "story", "list", {**data, "items": items[:5], "cta": "See live crowds 👆"}, en=title, bn=title, src="ig_story")]
        wa = self.wa(d, en, bn)
        return cards, wa

    def t_recap(self, d):
        total = sum(v.get("visits", 0) for v in self.stats.values()) if self.stats else 0
        cards = [self.card(d, "recap", "post", "hero", {
            "kicker": "শুভ বিজয়া · Subho Bijoya", "big": "🙏", "title": "Asche bochor abar hobe!",
            "subtitle": (f"{total:,} check-ins across {len(self.g['pandals'])} pandals. Thank you, Kolkata." if total else f"Thank you, Kolkata, for hopping {len(self.g['pandals'])} pandals with us."),
            "subtitle_bn": "আসছে বছর আবার হবে। ধন্যবাদ কলকাতা।", "cta": "Share your My Pujo card", "photo": self.photo("bagbazar")},
            en="Subho Bijoya 🙏 Asche bochor abar hobe! Share your My Pujo card (Me tab) and tag us. See you next year.",
            bn="শুভ বিজয়া 🙏 আসছে বছর আবার হবে! Me ট্যাব থেকে আমার পুজো কার্ড শেয়ার করে আমাদের ট্যাগ করুন।", src="ig_bio", tags="#SubhoBijoya #শুভবিজয়া")]
        cards.append(self.card(d, "recap", "story", "hero", {**cards[0]["data"], "cta": "Share your card 👆"},
                               en="Subho Bijoya! Share your My Pujo card 🙏", bn="শুভ বিজয়া! আমার পুজো কার্ড শেয়ার করুন 🙏", src="ig_story"))
        wa = self.wa(d, "🙏 Subho Bijoya! Share your pujo stats card from the Me tab.", "🙏 শুভ বিজয়া! Me ট্যাব থেকে আপনার পুজোর কার্ড শেয়ার করুন।")
        return cards, wa


# ---------------------------------------------------------------- page
def page(days, today):
    esc = html.escape
    by = {d["date"]: d for d in days}
    order = sorted(by)
    first = today.isoformat() if today.isoformat() in by else (order[0] if today < START else order[-1])

    def day_html(d):
        cards = "".join(f"""
      <article class="card">
        <img loading="lazy" src="{esc(c['file'])}" alt="{esc(c['id'])}" class="{c['format']}">
        <div class="meta"><b>{'Instagram post' if c['format'] == 'post' else 'Story / WhatsApp Status'}</b>
          <a class="btn" href="{esc(c['file'])}" download>Download</a></div>
        <label>Caption (English)<textarea readonly>{esc(c['caption_en'])}</textarea></label><button class="btn copy">Copy</button>
        <label>Caption (বাংলা)<textarea readonly>{esc(c['caption_bn'])}</textarea></label><button class="btn copy">Copy</button>
        <p class="fine">Link sticker / bio link: <code>{esc(c['link'])}</code> <button class="btn copy-link" data-v="{esc(c['link'])}">Copy link</button></p>
      </article>""" for c in d["cards"])
        w = d["whatsapp"]
        return f"""<section class="day" id="d{d['date']}" {'' if d['date'] == first else 'hidden'}>
      <h2>{dt.date.fromisoformat(d['date']).strftime('%a %d %b')} · {esc(d['theme'].replace('_', ' '))}</h2>
      <div class="grid">{cards}</div>
      <h3>WhatsApp</h3>
      <div class="grid">
        <article class="card"><b>Channel post</b><textarea readonly>{esc(w['channel'])}</textarea><button class="btn copy">Copy</button></article>
        <article class="card"><b>Forward to groups</b><textarea readonly>{esc(w['forward'])}</textarea>
          <div class="row"><button class="btn copy">Copy</button><a class="btn wa" target="_blank" rel="noopener" href="https://wa.me/?text={esc(urllib.parse.quote(w['forward']))}">Open WhatsApp</a></div></article>
      </div></section>"""

    tabs = "".join(f'<button class="tab" data-d="d{k}" aria-pressed="{str(k == first).lower()}">{dt.date.fromisoformat(k).strftime("%d %b")}</button>' for k in order)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>Pujo Parikrama · content kit</title>
<style>
:root{{--bg:#fff7ed;--ink:#1f2937;--card:#fff;--line:#fde3c7;--accent:#9F1239}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1c1917;--ink:#f5f5f4;--card:#292524;--line:#44403c}}}}
body{{margin:0;font:15px/1.45 system-ui,"Noto Sans Bengali",sans-serif;background:var(--bg);color:var(--ink)}}
header{{padding:16px;background:var(--accent);color:#fff}} header h1{{margin:0;font-size:20px}} header p{{margin:4px 0 0;opacity:.9}}
nav{{display:flex;gap:6px;overflow-x:auto;padding:10px 16px;position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line)}}
.tab{{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:99px;padding:6px 12px;white-space:nowrap}}
.tab[aria-pressed=true]{{background:var(--accent);color:#fff;border-color:var(--accent)}}
main{{padding:0 16px 40px;max-width:1100px;margin:auto}} .grid{{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(300px,1fr))}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px;display:flex;flex-direction:column;gap:8px}}
.card img{{width:100%;border-radius:10px;background:#0001}} .card img.story{{max-height:520px;object-fit:contain}}
textarea{{width:100%;min-height:120px;box-sizing:border-box;border-radius:8px;border:1px solid var(--line);background:transparent;color:inherit;font:inherit;padding:8px}}
label{{display:flex;flex-direction:column;gap:4px;font-weight:600}} .meta,.row{{display:flex;gap:8px;align-items:center;justify-content:space-between}}
.btn{{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:8px;padding:6px 10px;text-decoration:none;font:inherit;cursor:pointer}}
.btn.wa{{background:#25D366;color:#fff;border-color:#25D366}} .fine{{font-size:13px;opacity:.85;word-break:break-all}}
.posters{{margin-top:28px}}
</style></head><body>
<header><h1>🪔 Pujo Parikrama · daily content kit</h1><p>Post the cards, paste the captions, forward the WhatsApp text. Rebuilt every morning from the live guide.</p></header>
<nav>{tabs}</nav>
<main>{''.join(day_html(by[k]) for k in order)}
<section class="posters"><h2>Print and offline</h2>
<div class="grid"><article class="card"><b>QR posters (A4, one per pandal or eatery)</b><p>Each QR opens that place in the app and is counted as <code>qr_&lt;place&gt;</code>. Ask the puja committee or shop before putting one up.</p><a class="btn" href="posters.pdf" download>posters.pdf</a></article>
<article class="card"><b>General flyer</b><img src="flyer.png" alt="flyer"><a class="btn" href="flyer.png" download>flyer.png</a></article></div></section>
</main>
<script>
document.querySelector('nav').onclick=(e)=>{{const b=e.target.closest('.tab');if(!b)return;document.querySelectorAll('.tab').forEach(t=>t.setAttribute('aria-pressed',t===b));document.querySelectorAll('.day').forEach(s=>s.hidden=s.id!==b.dataset.d);}};
document.addEventListener('click',async(e)=>{{const b=e.target.closest('.copy,.copy-link');if(!b)return;const p=b.previousElementSibling,ta=p&&p.tagName==='TEXTAREA'?p:(p&&p.querySelector&&p.querySelector('textarea'))||b.closest('.card').querySelector('textarea');const v=b.dataset.v||ta.value;try{{await navigator.clipboard.writeText(v);b.textContent='Copied ✓';setTimeout(()=>b.textContent=b.classList.contains('copy-link')?'Copy link':'Copy',1500)}}catch{{prompt('Copy',v)}}}});
document.querySelector('.tab[aria-pressed=true]')?.scrollIntoView({{inline:'center'}});
</script></body></html>"""


def posters(g, n_pandals=40):
    top = sorted(g["pandals"], key=lambda p: (-p["popularity"], p["name"]))[:n_pandals]
    out = [{"id": p["id"], "name": p["name"], "name_bn": p.get("name_bn", ""), "kind": "pandal", "metro": p["nearest_metro"]["name"],
            "url": f"{SITE}?src=qr_{p['id'][:36]}#p={p['id']}"} for p in top]
    out += [{"id": f["id"], "name": f["name"].split(" (")[0], "name_bn": "", "kind": "food", "metro": f["nearest_metro"]["name"],
             "url": f"{SITE}?src=qr_{f['id'][:36]}#p={f['id']}"} for f in g["food"]]
    return out


def build(out, today=None, stats=None):
    g = json.loads((ROOT / "app" / "data" / "guide.json").read_text(encoding="utf-8"))
    today = today or dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date()
    kit = Kit(g, stats, today)
    days = []
    d = START
    while d <= END:
        days.append(kit.day(d)); d += dt.timedelta(days=1)
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    for day in days:
        (out / day["date"]).mkdir(exist_ok=True)
        (out / day["date"] / "assets.json").write_text(json.dumps(day, ensure_ascii=False, indent=1), encoding="utf-8")
    bundle = {"site": SITE, "today": today.isoformat(), "cards": [c for day in days for c in day["cards"]], "posters": posters(g),
              "flyer": {"url": f"{SITE}?src=qr_flyer", "pandals": len(g["pandals"])}}
    (out / "assets.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "index.html").write_text(page(days, today), encoding="utf-8")
    return bundle


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(ROOT / "app" / "kit"))
    ap.add_argument("--today", help="YYYY-MM-DD (default: today in IST)")
    ap.add_argument("--stats", help="place_stats JSON (array of rows) for live cards")
    a = ap.parse_args(argv)
    stats = None
    if a.stats and Path(a.stats).exists():
        try:
            stats = {r["place_id"]: r for r in json.loads(Path(a.stats).read_text(encoding="utf-8"))}
        except (ValueError, KeyError, TypeError):
            stats = None
    b = build(a.out, dt.date.fromisoformat(a.today) if a.today else None, stats)
    print(f"kit: {len(b['cards'])} cards over {len({c['date'] for c in b['cards']})} days, {len(b['posters'])} posters → {a.out}")


if __name__ == "__main__":
    main()
