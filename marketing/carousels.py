"""Instagram carousels for @pujoparikrama.guide: saveable, shareable, text-first slides (1080×1350).

    python -m marketing.carousels --out <dir>        # writes <dir>/carousels.json, <nn-slug>/caption.txt, index.md
    node marketing/carousels.mjs <dir>               # renders <nn-slug>/slide-01.jpg …

Every pandal, station, eatery, timing, quiet hour and route fact comes from app/data/guide.json, so a
carousel never disagrees with the app. Cultural explainers (rituals, words, tips) are general knowledge.
Slides never print the app's address: the handle and "link in bio" stand in for it. Stdlib only.
"""
import argparse
import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HANDLE = "@pujoparikrama.guide"
BASE_TAGS = ["#DurgaPuja2026", "#KolkataDurgaPuja", "#DurgaPujo", "#PandalHopping", "#Kolkata", "#PujoParikrama", "#দুর্গাপুজো", "#পুজো"]
CTA_EN = f"Save this 📌 · Plan your pujo free → link in bio · {HANDLE}"
LINE_ICON = {"blue": "🚇", "green": "🚇", "purple": "🚇", "orange": "🚇", "suburban": "🚆"}
LINE_NAME = {"blue": "Blue Line", "green": "Green Line", "purple": "Purple Line", "orange": "Orange Line", "suburban": "Suburban rail"}
CARS = {"avoid": "Cars: avoid", "limited": "Cars: limited", "ok": "Cars: OK"}
MAX_WORDS = 45  # English words per slide (brief says ~40; Bengali lines are extra)


# ---------------------------------------------------------------- small helpers
def hour_label(h):
    h %= 24
    return f"{(h % 12) or 12} {'am' if h < 12 else 'pm'}"


def hours_range(hours):
    """[5, 6] → '5–7 am' (the list holds start hours, so the window ends an hour after the last one)."""
    if not hours:
        return ""
    a, b = hours[0], (hours[-1] + 1) % 24
    sa, sb = hour_label(a), hour_label(b)
    if sa[-2:] == sb[-2:]:
        sa = sa[:-3]
    return f"{sa}–{sb}"


def clock(hhmm):
    h, m = map(int, hhmm.split(":"))
    return f"{(h % 12) or 12}{':%02d' % m if m else ''} {'am' if h < 12 else 'pm'}"


def open_hours(s):
    a, b = s.split("-")
    return f"{clock(a)}–{clock(b)}"


def fmt_date(iso, long=False):
    d = dt.date.fromisoformat(iso)
    return d.strftime("%A %-d %b" if long else "%a %-d %b")


def minutes(n):
    h, m = divmod(int(n), 60)
    return f"{h}h {m:02d}m" if h else f"{m} min"


def words(slide):
    """Rough English word count of what a slide prints (Bengali excluded)."""
    out = []

    def walk(v, key=""):
        if isinstance(v, str):
            if key in {"t", "theme", "icon", "emoji", "line"} or key.endswith("bn"):
                return
            out.extend(w for w in re.split(r"\s+", v) if re.search(r"[A-Za-z0-9]", w))
        elif isinstance(v, list):
            for x in v:
                walk(x, key)
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(x, k)
    walk(slide)
    return len(out)


def chunks(xs, n):
    return [xs[i:i + n] for i in range(0, len(xs), n)]


# ---------------------------------------------------------------- builder
class Carousels:
    def __init__(self, g):
        self.g = g
        self.p = {p["id"]: p for p in g["pandals"]}
        self.f = {f["id"]: f for f in g["food"]}
        self.z = {z["id"]: z for z in g["zones"]}
        self.r = {r["id"]: r for r in g["regions"]}
        self.st = {t["id"]: t for t in g["transit"]}
        self.days = {d["id"]: d for d in g["meta"]["days"]}
        self.trails = {i["id"]: i for i in g["itineraries"]}
        hf = g["meta"]["model"]["hour_factors"]
        top = max(hf)
        self.peak_hours = [h for h, v in enumerate(hf) if v >= top]          # [19, 20, 21]
        self.quiet_all = self._common_quiet()                                  # [5, 6] if shared by every pandal

    def _common_quiet(self):
        sets = [set(h) for p in self.g["pandals"] for h in p["quiet_hours"].values()]
        common = set.intersection(*sets) if sets else set()
        return sorted(common)

    # --- shared bits
    def metro(self, p):
        m = p.get("nearest_metro")
        if not m:
            return ""
        name = m["name"].split(" (")[0].replace("Sovabazar Sutanuti", "Sovabazar").replace("Mahatma Gandhi Road", "MG Road")
        if m["line"] == "suburban":
            name = name.replace("Junction", "Jn") + " rail"
        txt = f"{LINE_ICON.get(m['line'], '🚇')} {name} · {m['walk_min']} min"
        return txt + (" · auto/cab" if m["walk_min"] > 30 else "")

    def pandal_item(self, p, pill=True):
        return {"name": p["name"], "bn": p.get("name_bn") or "", "meta": self.metro(p),
                "pill": p["best_slot_label"] if pill else ""}

    def cta(self, bn="সেভ করে রাখুন · বন্ধুদের পাঠান · প্ল্যান করুন ফ্রি-তে"):
        return {"t": "cta", "theme": "red", "bn": bn}

    def carousel(self, slug, title, date, slides, en, bn, tags):
        tags = BASE_TAGS + [t for t in tags if t not in BASE_TAGS]
        assert 8 <= len(tags) <= 12, (slug, len(tags))
        return {"slug": slug, "title": title, "date": date, "slides": slides,
                "caption_en": en.strip(), "caption_bn": bn.strip(), "hashtags": " ".join(tags)}

    # ---------------------------------------------------------------- carousels
    def quiet_cheatsheet(self):
        ids = ["tala_prattoy", "kumartuli_park", "sreebhumi", "bagbazar", "md_ali_park",
               "santosh_mitra", "college_square", "ekdalia", "tridhara", "suruchi_sangha"]
        ps = [self.p[i] for i in ids]
        q = hours_range(self.quiet_all)
        peak = hours_range(self.peak_hours)
        items = [self.pandal_item(p) for p in ps]
        parts = [items[:4], items[4:7], items[7:]]
        slides = [
            {"t": "cover", "theme": "red", "kicker": "Pujo 2026 cheat sheet", "title": "Skip the crowd at Kolkata's top 10",
             "accent": q, "sub": "When each big pandal is least crowded, from our crowd model.",
             "bn": "সেরা ১০টা পুজো, কখন গেলে ভিড় সবচেয়ে কম", "tag": "SAVE BEFORE SHASHTHI 📌"},
            {"t": "stats", "theme": "cream", "title": "The two numbers to remember",
             "stats": [{"v": q, "l": "quietest window at every pandal, every puja day"},
                       {"v": peak, "l": "peak crowd hours across the city"}],
             "note": "Can't do dawn? Each pandal's 'Best' slot is its next-best window."},
        ]
        for i, part in enumerate(parts):
            a, b = [(1, 4), (5, 7), (8, 10)][i]
            slides.append({"t": "list", "theme": "red", "kicker": f"Top 10 · {a}–{b}",
                           "title": ["North", "Central", "South"][i], "items": part, "start": a,
                           "note": f"Pill = best slot · all quietest {q}"})
        slides.append(self.day_bars("Which day is calmest?"))
        slides.append(self.cta())
        return self.carousel("quiet-hours-top-10", "Quiet-hours cheat sheet: top 10 pandals", "2026-10-05", slides,
                             f"""Want Tala Prattoy, Sreebhumi or Md. Ali Park without a 2-hour queue? 🪔
Our crowd model says every pandal is quietest {q}, and the city peaks {peak}. Here's the best slot for Kolkata's 10 biggest, plus which puja day is calmest.
Save this and send it to your pandal-hopping gang 📌 Plan your route free → link in bio.""",
                             f"""টালা প্রত্যয়, শ্রীভূমি বা মহম্মদ আলি পার্ক — লম্বা লাইন ছাড়া দেখতে চান? 🪔
সব প্যান্ডেলেই ভিড় সবচেয়ে কম ভোর {q}-এ। কোন পুজো কখন গেলে ভালো, আর কোন দিন ভিড় কম — সব এক জায়গায়।
সেভ করে রাখুন, ঠাকুর দেখার দলকে পাঠান 📌 ফ্রি প্ল্যান করুন → বায়োতে লিংক।""",
                             ["#QuietHours", "#TalaPrattoy", "#Sreebhumi"])

    def day_bars(self, title):
        base = self.days["saptami"]["factor"]
        bars = [{"label": d["name"], "bn": d["name_bn"], "date": fmt_date(d["date"]), "v": round(100 * d["factor"] / base)}
                for d in self.g["meta"]["days"] if d["id"] != "mahalaya"]
        return {"t": "bars", "theme": "dark", "title": title, "bars": bars,
                "note": "Expected crowd, Saptami = 100. Panchami & Shashthi run lighter."}

    # --- regions
    def region(self, rid, slug, title, hook, date, n=12, extra_tags=(), food_n=4, bonus=None):
        reg = self.r[rid]
        zs = reg["zone_ids"]
        ps = sorted([p for p in self.g["pandals"] if p["zone"] in zs and p["popularity"] >= 3],
                    key=lambda p: (-p["popularity"], -p["peak_crowd"], p["name"]))[:n]
        zones = [self.z[z] for z in zs if any(p["zone"] == z for p in ps)]
        slides = [{"t": "cover", "theme": "red", "kicker": f"{reg['name']} Kolkata · {reg['name_bn']}", "title": hook["title"],
                   "accent": hook.get("accent", ""), "sub": hook["sub"], "bn": hook["bn"], "tag": "SAVE FOR PANDAL HOPPING 📌"}]
        zitems = [{"icon": "📍", "name": z["name"], "bn": z.get("name_bn", ""),
                   "meta": f"Start: {self.st[z['entry_station']]['name']} · {CARS.get(z.get('car_advisory'), '')}"} for z in zones[:4]]
        slides.append({"t": "list", "theme": "cream", "kicker": "The areas", "title": "Where to start", "items": zitems})
        main = zones[0]
        slides.append({"t": "tip", "theme": "dark", "icon": "🚶", "kicker": main["short"], "title": "Getting around",
                       "body": main["walk_tip"]})
        start = 1
        for i, part in enumerate(chunks(ps, 4)):
            slides.append({"t": "list", "theme": "red", "kicker": f"Must-see · {start}–{start + len(part) - 1}",
                           "title": "Metro · best time", "items": [self.pandal_item(p) for p in part], "start": start})
            start += len(part)
        foods = [self.f[fid] for z in zones for fid in z.get("food_ids", [])][:food_n]
        if foods:
            slides.append({"t": "list", "theme": "cream", "kicker": "Refuel", "title": "Eat here between pandals",
                           "items": [self.food_item(f) for f in foods]})
        if bonus:
            slides.append(bonus)
        slides.append(self.cta())
        return self.carousel(slug, hook.get("name", f"{reg['name']} Kolkata pandal guide"), date, slides, hook["en"], hook["bn_cap"],
                             list(extra_tags))

    def food_item(self, f, near=True):
        np_ = [self.p[i]["name"] for i in f.get("near_pandals", []) if i in self.p]
        where = f"Near {np_[0]}" if (near and np_) else f"{self.z[f['zone']]['short']} · till {clock(f['hours'].split('-')[1])}"
        return {"icon": {"sweets": "🍬", "cabin": "🍽️", "restaurant": "🍛", "street": "🥟", "drinks": "🥤"}.get(f["type"], "🍴"),
                "name": f["name"].split(" (")[0], "meta": "👉 " + ", ".join(f["dishes"][:2]), "meta2": where}

    def regions(self):
        out = []
        out.append(self.region("north", "north-kolkata", "North Kolkata", {
            "title": "North Kolkata, sorted", "accent": "Kumartuli → Tala → Sreebhumi",
            "sub": "Heritage lanes, theme blockbusters, nearest metro and walk time for each.",
            "bn": "উত্তর কলকাতার সেরা পুজো, মেট্রো আর হাঁটার সময়",
            "en": """North Kolkata in one save 🪔
Kumartuli Park, Tala Prattoy, Bagbazar, Sovabazar Rajbari, Sreebhumi and more, each with its nearest metro, the walk time and the best time to go. Plus where to start and where to eat (hello, Mitra Cafe kabiraji).
Save it, tag your North gang 📌 Full map and routes free → link in bio.""",
            "bn_cap": """উত্তর কলকাতা, এক পোস্টে 🪔
কুমোরটুলি পার্ক, টালা প্রত্যয়, বাগবাজার, শোভাবাজার রাজবাড়ি, শ্রীভূমি — কোন মেট্রো, কত মিনিট হাঁটা, কখন যাবেন। সঙ্গে কোথায় খাবেন।
সেভ করুন, উত্তরের বন্ধুদের ট্যাগ করুন 📌 ফ্রি ম্যাপ → বায়োতে লিংক।"""}, "2026-10-04", n=12,
            extra_tags=["#NorthKolkata", "#Kumartuli", "#Bagbazar"]))
        out.append(self.region("central", "central-kolkata", "Central Kolkata", {
            "title": "Central Kolkata's theme giants", "accent": "Md. Ali Park · College Sq · Lebutala",
            "sub": "Huge queues, huge spectacle. Here's how to do them smart.",
            "bn": "মধ্য কলকাতার বড় পুজো: কোন মেট্রো, কখন যাবেন",
            "en": """Central Kolkata = the blockbusters 🪔
Md. Ali Park, College Square, Santosh Mitra Square (Lebutala), Chaltabagan and more, with nearest metro, walk time and best time to go. Then kochuri at Putiram and sherbet at Paramount.
Save this before Saptami 📌 Plan it free → link in bio.""",
            "bn_cap": """মধ্য কলকাতার বড় পুজো 🪔
মহম্মদ আলি পার্ক, কলেজ স্কোয়ার, সন্তোষ মিত্র স্কোয়ার (লেবুতলা), চালতাবাগান — কোন মেট্রো, কত মিনিট হাঁটা, কখন গেলে ভিড় কম। তারপর পুঁটিরামের কচুরি।
সপ্তমীর আগে সেভ করে রাখুন 📌 ফ্রি প্ল্যান → বায়োতে লিংক।"""}, "2026-10-06", n=8,
            extra_tags=["#CentralKolkata", "#CollegeSquare", "#MdAliPark"]))
        out.append(self.region("south", "south-kolkata", "South Kolkata", {
            "title": "South Kolkata heavyweights", "accent": "Ekdalia · Tridhara · Suruchi",
            "sub": "The densest pandal belt in the city, with metro + walk times.",
            "bn": "দক্ষিণের হেভিওয়েট পুজো, মেট্রো আর হাঁটার সময়",
            "en": """South Kolkata heavyweights 🪔
Ekdalia, Singhi Park, Tridhara, Chetla Agrani, Suruchi Sangha, Maddox Square, Badamtala and more, each with its nearest metro, walk time and best time to go. Phuchka stop included.
Save it, send it to the South para group 📌 Free routes → link in bio.""",
            "bn_cap": """দক্ষিণের হেভিওয়েট 🪔
একডালিয়া, সিংহী পার্ক, ত্রিধারা, চেতলা অগ্রণী, সুরুচি সংঘ, ম্যাডক্স স্কোয়ার, বাদামতলা — কোন মেট্রো, কত মিনিট হাঁটা, কখন যাবেন। ফুচকার ঠিকানাও আছে।
সেভ করুন, পাড়ার গ্রুপে পাঠান 📌 ফ্রি রুট → বায়োতে লিংক।"""}, "2026-10-05", n=12,
            extra_tags=["#SouthKolkata", "#Ekdalia", "#SuruchiSangha"]))
        hz = self.z["howrah"]
        bonus = {"t": "tip", "theme": "dark", "icon": "⛴️", "kicker": "Bonus · Across the river", "title": hz["name"],
                 "body": f"{hz['vibe']} {hz['walk_tip']}", "bn": hz.get("name_bn", "")}
        out.append(self.region("east", "salt-lake-east-howrah", "Salt Lake, East & Howrah", {
            "title": "Salt Lake, East & Howrah", "name": "Salt Lake, East & Howrah pandal guide", "accent": "Family-friendly pujo",
            "sub": "Wide roads, organised blocks, and a quieter Howrah bonus.",
            "bn": "সল্টলেক, পূর্ব কলকাতা আর হাওড়ার পুজো",
            "en": """Pujo with the family? Start in Salt Lake 🪔
FD Block, BJ Block, AE Block and the other Salt Lake blocks, with nearest metro, walk time and best time to go. Plus where to eat, and a bonus: the quieter, local pujas across the river in Howrah.
Save it for the family outing 📌 Free planner → link in bio.""",
            "bn_cap": """পরিবার নিয়ে ঠাকুর দেখা? সল্টলেক দিয়ে শুরু করুন 🪔
এফডি ব্লক, বিজে ব্লক, এই ব্লক আর অন্য ব্লকের পুজো — কোন মেট্রো, কত মিনিট হাঁটা, কখন যাবেন। বোনাস: নদীর ওপারে হাওড়ার শান্ত পুজো।
সেভ করে রাখুন 📌 ফ্রি প্ল্যানার → বায়োতে লিংক।"""}, "2026-10-07", n=8,
            extra_tags=["#SaltLake", "#Howrah", "#FDBlock"], bonus=bonus))
        return out

    # --- trails
    def trail(self, tid, date):
        t = self.trails[tid]
        day = self.days[t["day"]]
        tot = t["totals"]
        rows = []
        n = 0
        for seg in t["segments"]:
            if seg["type"] == "ride":
                rows.append({"badge": clock(seg["depart"]), "ride": True, "name": f"Ride to {self.st[seg['to_station']]['name'].split(' (')[0]}",
                             "meta": f"➜ {seg['ride_min']} min ride"})
                continue
            for s in seg["stops"]:
                n += 1
                p = self.p[s["pandal"]]
                crowd = s["crowd"]
                level = "Low" if crowd < 40 else ("Medium" if crowd < 70 else "Busy")
                rows.append({"badge": clock(s["arrive"]), "name": p["name"], "meta": f"🚶 {s['walk_min']} min walk",
                             "pill": level, "level": "lo" if crowd < 40 else ("mid" if crowd < 70 else "hi")})
        start_st = self.st[t["segments"][0]["start"]]["name"]
        slides = [{"t": "cover", "theme": "red", "kicker": f"Pujo trail · {day['name']} {fmt_date(day['date'])}",
                   "title": t["name"], "bn": t["name_bn"],
                   "sub": t["blurb"], "accent": f"{t['pandal_count']} pandals · {tot['walk_km']:g} km",
                   "tag": "SAVE THE ROUTE 📌"},
                  {"t": "stats", "theme": "cream", "title": "The trail in numbers",
                   "stats": [{"v": f"{clock(t['start_time'])}", "l": f"start at {start_st}"},
                             {"v": minutes(tot["duration_min"]), "l": f"end around {clock(t['end_time'])}"},
                             {"v": f"{tot['steps']:,}", "l": "steps"},
                             {"v": f"{tot['walk_km']:g} km", "l": f"walking{' + ' + str(tot['ride_min']) + ' min rides' if tot['ride_min'] else ''}"}],
                   "note": f"Planned for {day['name']} ({fmt_date(day['date'])}). Times shift if you start later."}]
        k = -(-len(rows) // 4)                       # pages of at most 4 rows, balanced
        pages = [rows[round(i * len(rows) / k):round((i + 1) * len(rows) / k)] for i in range(k)]
        for i, part in enumerate(pages):
            slides.append({"t": "list", "theme": "red" if i % 2 == 0 else "dark", "kicker": f"Arrive · pandal · crowd · {i + 1}/{len(pages)}",
                           "title": "Your route", "items": part})
        zones = [seg["zone"] for seg in t["segments"] if seg["type"] == "walk"]
        foods = [self.f[fid] for z in zones for fid in self.z[z].get("food_ids", [])][:4]
        if foods:
            slides.append({"t": "list", "theme": "cream", "kicker": "Refuel on the route", "title": "Eat here",
                           "items": [self.food_item(f) for f in foods]})
        slides.append(self.cta())
        names = [self.p[s["pandal"]]["name"] for seg in t["segments"] if seg["type"] == "walk" for s in seg["stops"]]
        first = ", ".join(names[:4])
        en = f"""{t['name']}: a ready-made route for {day['name']} ({fmt_date(day['date'], True)}) 🪔
{t['blurb']}
{t['pandal_count']} pandals in order, starting {clock(t['start_time'])} from {start_st}: {first} and more. {tot['walk_km']:g} km, about {tot['steps']:,} steps, with arrival times and crowd levels for each stop.
Save it and tag who's coming 📌 Live version with maps → link in bio."""
        bn = f"""{t['name_bn']} 🪔
{t['blurb_bn']}
{day['name_bn']}-র রুট: {t['pandal_count']}টা প্যান্ডেল, পরপর সাজানো — কখন পৌঁছবেন, কতটা ভিড়, সব দেওয়া আছে। মোট {tot['walk_km']:g} কিমি হাঁটা।
সেভ করুন, সঙ্গীদের ট্যাগ করুন 📌 ম্যাপসহ রুট → বায়োতে লিংক।"""
        tag = {"north_heritage": ["#NorthKolkata", "#HeritageWalk"], "central_blockbusters": ["#CentralKolkata", "#CollegeSquare"],
               "south_classic": ["#SouthKolkata", "#Ekdalia"], "behala_trail": ["#Behala", "#SuruchiSangha"],
               "east_hop": ["#SaltLake", "#Sreebhumi"], "all_nighter": ["#AllNighter", "#Ashtami"]}[tid]
        return self.carousel(f"trail-{tid.replace('_', '-')}", f"Trail: {t['name']}", date, slides, en, bn, tag + ["#PujoTrail"])

    def trails_all(self):
        # Post each trail a few days before the day it is planned for.
        when = {"east_hop": "2026-10-13", "behala_trail": "2026-10-14", "central_blockbusters": "2026-10-15",
                "north_heritage": "2026-10-16", "all_nighter": "2026-10-17", "south_classic": "2026-10-18"}
        return [self.trail(tid, when.get(tid, "2026-10-12")) for tid in self.trails]

    # --- metro
    def metro_sheet(self):
        by = {}
        for p in self.g["pandals"]:
            m = p.get("nearest_metro")
            if not m or m["line"] == "suburban" or m["walk_min"] > 15 or p["popularity"] < 3:
                continue
            by.setdefault(m["id"], []).append((m["walk_min"], p["name"]))
        order = [t["id"] for t in self.g["transit"] if t["id"] in by]
        items = []
        for sid in order:
            st = self.st[sid]
            ps = sorted(by[sid])
            items.append({"name": st["name"], "line": st["line"], "chip": LINE_NAME[st["line"]],
                          "rows": [f"{n.split(' (')[0]} · {w} min" for w, n in ps[:3]]})
        slides = [{"t": "cover", "theme": "red", "kicker": "Metro cheat sheet", "title": "Get off here, walk there",
                   "accent": f"{len(items)} stations", "sub": "Every metro station with a well-known pandal within a 15-minute walk.",
                   "bn": "কোন মেট্রো স্টেশনে নামলে কোন পুজো হাঁটা পথে", "tag": "SCREENSHOT THIS 📲"}]
        pages = []
        for line in dict.fromkeys(x["line"] for x in items):
            xs = [x for x in items if x["line"] == line]
            k = -(-len(xs) // 4)
            pages += [(line, j + 1, k, xs[round(j * len(xs) / k):round((j + 1) * len(xs) / k)]) for j in range(k)]
        for i, (line, j, k, part) in enumerate(pages):
            slides.append({"t": "stations", "theme": "red" if i % 2 == 0 else "dark", "kicker": "Station → pandals (walk)",
                           "title": LINE_NAME[line] + (f" · {j}/{k}" if k > 1 else ""), "items": part})
        sw = self.z["southwest"]
        slides.append({"t": "tip", "theme": "cream", "icon": "💡", "kicker": "Metro tips", "title": "Leave the car at home",
                       "body": f"{self.z['central']['walk_tip']} {sw['walk_tip'].split('.')[0]}."})
        slides.append(self.cta())
        return self.carousel("metro-cheat-sheet", "Metro cheat sheet: station → pandals", "2026-10-06", slides,
                             """Pandal hopping by metro? Screenshot this 🚇🪔
Every station with a well-known pandal inside a 15-minute walk: Sovabazar for Sovabazar Rajbari, Kalighat for Badamtala, MG Road for Md. Ali Park, Belgachia for Tala Prattoy, City Centre for FD Block and the Purple Line for Behala.
Save it 📌 Full walking routes free → link in bio.""",
                             """মেট্রোয় ঠাকুর দেখা? স্ক্রিনশট নিয়ে রাখুন 🚇🪔
কোন স্টেশনে নামলে ১৫ মিনিট হাঁটায় কোন পুজো: শোভাবাজার রাজবাড়ির জন্য শোভাবাজার, বাদামতলার জন্য কালীঘাট, মহম্মদ আলি পার্কের জন্য এমজি রোড, টালা প্রত্যয়ের জন্য বেলগাছিয়া।
সেভ করুন 📌 ফ্রি হাঁটার রুট → বায়োতে লিংক।""",
                             ["#KolkataMetro", "#MetroRide", "#PujoGuide"])

    # --- food
    def food_map(self):
        F = self.f
        north = ["mitra_cafe", "golbari", "allens_kitchen", "girish_nakur"]
        central = ["putiram", "paramount", "coffee_house", "bhim_nag"]
        central2 = ["royal_indian", "aminia", "nizams"]
        south = ["vivekananda_park_phuchka", "bhojohori_manna", "kewpies", "balwant_singh"]
        late = sorted([f for f in self.g["food"] if f["hours"].split("-")[1] in ("00:00", "01:00", "02:00")],
                      key=lambda f: (f["hours"].split("-")[1] != "02:00", f["name"]))[:4]
        slides = [{"t": "cover", "theme": "red", "kicker": "Pujo food map", "title": "Where to eat between pandals",
                   "accent": "and what to order", "sub": "Iconic cabins, sweet shops and stalls next to the big pujas.",
                   "bn": "প্যান্ডেলের পাশে কোথায় খাবেন, কী অর্ডার করবেন", "tag": "SAVE FOR PET PUJO 📌"}]
        for k, (title, ids) in enumerate([("North: cutlets & sandesh", north), ("College Street & Sealdah", central),
                                          ("Biryani, chaap & rolls", central2), ("South: phuchka to paturi", south)]):
            slides.append({"t": "list", "theme": "cream" if k % 2 else "red", "kicker": "Food map", "title": title,
                           "items": [self.food_item(F[i]) for i in ids]})
        slides.append({"t": "list", "theme": "dark", "kicker": "Open past midnight", "title": "Late-night fuel 🌙",
                       "items": [self.food_item(f, near=False) for f in late]})
        slides.append(self.cta(bn="সেভ করুন · খাদ্যরসিক বন্ধুকে ট্যাগ করুন"))
        return self.carousel("pujo-food-map", "Pujo food map: what to order near the pandals", "2026-10-08", slides,
                             """Pandal hopping is 50% thakur, 50% food. Here's the food half 🍗🪔
Mitra Cafe's fish kabiraji, Golbari's kosha mangsho, Putiram's kochuri, Paramount's daab sherbet, Bhim Chandra Nag's ledikeni, Vivekananda Park phuchka, and the stalls that stay open till 1–2 am.
Save it and tag your food partner 📌 Food near every pandal → link in bio.""",
                             """ঠাকুর দেখা অর্ধেক, খাওয়া বাকি অর্ধেক 🍗🪔
মিত্র ক্যাফের ফিশ কবিরাজি, গোলবাড়ির কষা মাংস, পুঁটিরামের কচুরি, প্যারামাউন্টের ডাব শরবত, ভীম চন্দ্র নাগের লেডিকেনি, বিবেকানন্দ পার্কের ফুচকা — আর রাত একটা-দুটো পর্যন্ত খোলা স্টল।
সেভ করুন, খাদ্যসঙ্গীকে ট্যাগ করুন 📌 প্রতিটা প্যান্ডেলের কাছের খাবার → বায়োতে লিংক।""",
                             ["#KolkataFood", "#PetPujo", "#Kabiraji"])

    # --- general knowledge carousels
    def survival(self):
        tips = [
            ("👟", "Comfy shoes, not new ones", "Save the new pujo shoes for photos. Pack plasters for blisters."),
            ("🔋", "Power bank", "Maps, UPI and photos drain a phone fast. Charge it fully before you leave."),
            ("💰", "Small cash + UPI", "Networks jam in big crowds. Keep ₹10–₹100 notes for stalls and autos."),
            ("💧", "Water + ORS", "It gets hot and humid in the queues. Refill whenever you can."),
            ("📍", "A meeting point", "Fix a landmark at every pandal in case someone gets lost or a phone dies."),
            ("☂️", "Small umbrella", "October showers happen. A compact umbrella or poncho saves the outfit."),
            ("👜", "Front-facing bag", "Crowds mean pickpockets. Zip it, wear it in front, keep valuables close."),
            ("🧻", "Tissues & sanitiser", "For phuchka hands, sweat and the odd queue toilet."),
        ]
        slides = [{"t": "cover", "theme": "red", "kicker": "Pandal-hopping survival kit", "title": "Pack this before you go",
                   "accent": "8 essentials", "sub": "From the people who've walked 20,000 steps in new shoes and regretted it.",
                   "bn": "ঠাকুর দেখতে বেরোনোর আগে ব্যাগে যা রাখবেন", "tag": "SAVE · SEND TO THE GROUP 📌"}]
        for i, pair in enumerate(chunks(tips, 2)):
            slides.append({"t": "tips", "theme": ["cream", "red", "dark", "cream"][i],
                           "kicker": f"Survival kit · {i * 2 + 1}–{i * 2 + 2}",
                           "items": [{"icon": a, "title": b, "body": c} for a, b, c in pair]})
        slides.append({"t": "tip", "theme": "dark", "icon": "🚇", "kicker": "Bonus", "title": "Go by metro",
                       "body": "Cars crawl near the big pandals and many lanes close in the evening. Metro + walking is faster."})
        slides.append(self.cta())
        return self.carousel("survival-kit", "Pandal-hopping survival kit", "2026-10-09", slides,
                             """Your pandal-hopping survival kit 🎒🪔
Comfy shoes, a power bank, small cash + UPI, water, a meeting point, an umbrella, a front-facing bag and tissues. Simple, but nobody remembers all eight at 6 pm on Saptami.
Save this and send it to the group chat 📌 Plan routes, quiet hours and food free → link in bio.""",
                             """ঠাকুর দেখার সারভাইভাল কিট 🎒🪔
আরামদায়ক জুতো, পাওয়ার ব্যাংক, খুচরো টাকা + ইউপিআই, জল, দেখা করার জায়গা, ছাতা, সামনে ঝোলানো ব্যাগ আর টিস্যু।
সেভ করুন, গ্রুপে পাঠান 📌 ফ্রি রুট, কম ভিড়ের সময়, খাবার → বায়োতে লিংক।""",
                             ["#PujoTips", "#PujoShopping", "#Pujo2026"])

    def dates(self):
        D = self.days
        cells = [{"top": fmt_date(d["date"]), "big": d["name"], "bn": d["name_bn"], "hi": d["id"] == "ashtami"} for d in self.g["meta"]["days"]]
        info = [
            ("mahalaya", "🌅", "Devi Paksha begins. Dawn radio 'Mahishasuramardini', tarpan at the ghats, and the pujo countdown is on."),
            ("shashthi", "🪔", "Panchami: pandals open, crowds still light. Shashthi: Bodhon, the goddess is welcomed and unveiled."),
            ("saptami", "🌿", "At dawn the Kola Bou (Nabapatrika) is bathed and placed beside Ganesh. The first full puja day."),
            ("ashtami", "🌸", "Morning anjali in new clothes, Kumari Puja in many places, and Sandhi Puja with 108 lamps and lotuses."),
            ("navami", "🍛", "Navami bhog, dhunuchi naach to the dhak, and the last big night of pandal hopping."),
            ("dashami", "🔴", "Sindoor khela, bisarjan, and 'Shubho Bijoya': touch elders' feet, hug, share sweets."),
        ]
        slides = [{"t": "cover", "theme": "red", "kicker": "Durga Puja 2026 · Kolkata", "title": "Pujo dates 2026",
                   "accent": f"{fmt_date(D['mahalaya']['date'])} → {fmt_date(D['dashami']['date'])}",
                   "sub": "Mahalaya to Dashami, with what happens on each day.",
                   "bn": "মহালয়া থেকে দশমী: পুজোর দিনক্ষণ ২০২৬", "tag": "SAVE THE DATES 📌"},
                  {"t": "grid", "theme": "cream", "title": "Mark your calendar", "cells": cells}]
        for did, icon, body in info:
            d = D[did]
            title = f"{d['name']}" if did != "shashthi" else "Panchami & Shashthi"
            when = fmt_date(d["date"], True) if did != "shashthi" else f"{fmt_date(D['panchami']['date'])} & {fmt_date(d['date'])}"
            bn = d["name_bn"] if did != "shashthi" else f"{D['panchami']['name_bn']} ও {d['name_bn']}"
            slides.append({"t": "tip", "theme": "dark" if did in ("ashtami", "dashami") else "red", "icon": icon,
                           "kicker": when, "title": title, "bn": bn, "body": body})
        slides.append(self.day_bars("Crowd forecast by day"))
        slides.append(self.cta(bn="সেভ করে রাখুন · পরিবারের গ্রুপে পাঠান"))
        return self.carousel("pujo-dates-2026", "Pujo dates 2026: Mahalaya to Dashami", "2026-10-03", slides,
                             f"""Durga Puja 2026 dates, all in one place 🗓️🪔
Mahalaya {fmt_date(D['mahalaya']['date'], True)} · Panchami {fmt_date(D['panchami']['date'])} · Shashthi {fmt_date(D['shashthi']['date'])} · Saptami {fmt_date(D['saptami']['date'])} · Ashtami {fmt_date(D['ashtami']['date'])} · Navami {fmt_date(D['navami']['date'])} · Dashami {fmt_date(D['dashami']['date'])}.
What happens each day, and which day is busiest (spoiler: Ashtami).
Save it and send it to the family group 📌 Plan your pujo free → link in bio.""",
                             f"""দুর্গাপুজো ২০২৬-এর দিনক্ষণ 🗓️🪔
মহালয়া ১০ অক্টোবর, পঞ্চমী ১৬, ষষ্ঠী ১৭, সপ্তমী ১৮, অষ্টমী ১৯, নবমী ২০, দশমী ২১ অক্টোবর।
কোন দিন কী হয়, আর কোন দিন সবচেয়ে বেশি ভিড় (অষ্টমী!)।
সেভ করুন, পরিবারের গ্রুপে পাঠান 📌 ফ্রি প্ল্যান → বায়োতে লিংক।""",
                             ["#Mahalaya", "#Ashtami", "#Pujo2026"])

    def words_(self):
        groups = [
            ("The rituals", [("Bodhon", "বোধন", "The 'awakening': the goddess is invoked and welcomed on Shashthi evening."),
                             ("Kola Bou", "কলাবউ", "A banana plant draped in a red-bordered sari, bathed at dawn on Saptami."),
                             ("Anjali", "অঞ্জলি", "Offering flowers while chanting with the priest. Many fast until Ashtami anjali.")]),
            ("The big moments", [("Sandhi Puja", "সন্ধিপুজো", "At the Ashtami–Navami junction, with 108 lamps and 108 lotuses."),
                                 ("Kumari Puja", "কুমারী পুজো", "A young girl is worshipped as the goddess, usually on Ashtami."),
                                 ("Bhog", "ভোগ", "Food offered to the goddess and shared: khichuri, labra, payesh.")]),
            ("The sound of pujo", [("Dhak", "ঢাক", "The big drum. You'll hear it before you see the pandal."),
                                   ("Dhunuchi naach", "ধুনুচি নাচ", "Dancing to the dhak with a smoking clay incense burner."),
                                   ("Thakur dekha", "ঠাকুর দেখা", "Literally 'seeing the goddess'. Kolkata's word for pandal hopping.")]),
            ("The goodbye", [("Sindoor khela", "সিঁদুর খেলা", "On Dashami, married women offer sindoor to the goddess and to each other."),
                             ("Bisarjan", "বিসর্জন", "The immersion of the idol in the river or a pond."),
                             ("Bijoya", "বিজয়া", "After immersion: touch elders' feet, hug, share sweets. 'Shubho Bijoya!'")]),
            ("The pujas", [("Sarbojanin", "সর্বজনীন", "A community puja, open to all. Most pandals you visit are one."),
                           ("Bonedi bari", "বনেদি বাড়ি", "An old family's puja at their ancestral home."),
                           ("Daker saaj", "ডাকের সাজ", "Shimmering white-silver decoration on a traditional idol.")]),
        ]
        slides = [{"t": "cover", "theme": "red", "kicker": "For every probashi Bengali", "title": "Pujo words you should know",
                   "accent": "15 words", "sub": "So you know your Bodhon from your Bijoya.",
                   "bn": "পুজোর ১৫টা শব্দ — প্রবাসী বাঙালির জন্য", "tag": "SAVE · SEND TO A PROBASHI 📌"}]
        for i, (title, ws) in enumerate(groups):
            slides.append({"t": "words", "theme": ["cream", "red", "dark", "red", "cream"][i], "kicker": f"Pujo words · {i + 1}/5",
                           "title": title, "items": [{"name": a, "bn": b, "meta": c} for a, b, c in ws]})
        slides.append(self.cta(bn="সেভ করুন · প্রবাসী বন্ধুকে পাঠান"))
        return self.carousel("pujo-words", "Pujo words every probashi should know", "2026-10-04", slides,
                             """Bodhon, Kola Bou, Sandhi Puja, Bhog, Dhunuchi naach, Sindoor khela, Bijoya…
15 pujo words with a one-line meaning each, for every probashi Bengali (and every friend who's coming to Kolkata for the first time) 🪔
Save it and send it to someone who'll be at their first pujo 📌 Plan your pujo free → link in bio.""",
                             """বোধন, কলাবউ, সন্ধিপুজো, ভোগ, ধুনুচি নাচ, সিঁদুর খেলা, বিজয়া…
পুজোর ১৫টা শব্দ, এক লাইনে মানে — প্রবাসী বাঙালি আর প্রথমবার কলকাতার পুজো দেখতে আসা বন্ধুদের জন্য 🪔
সেভ করুন, পাঠিয়ে দিন 📌 ফ্রি প্ল্যান → বায়োতে লিংক।""",
                             ["#Probashi", "#BengaliCulture", "#SindoorKhela"])

    def hoppers(self):
        bt = self.trails["behala_trail"]["totals"]["steps"]
        tp = self.p["tala_prattoy"]
        types = [
            ("⏰", "The Ashtami Anjali Alarm", "Up at 5, fasting, freshly ironed, done with anjali before the rest of you have woken up."),
            ("🍗", "The Kabiraji Pilgrim", "'Pandal hopping' is a cover story. The route is Mitra Cafe → Golbari → phuchka → repeat."),
            ("🧐", "The Theme Critic", "Rates every pandal out of 10. 'Last year's was better.' Every year."),
            ("🏛️", "The North-Only Purist", "Kumartuli lanes, bonedi bari, Bagbazar. 'South-e ki dekhbo?'"),
            ("🌙", "The All-Nighter", "Starts at 10 pm, ends with dawn tea in South Kolkata. Sleeps on Dashami."),
            ("👟", "The Step Counter", f"Here for the bragging rights. The Behala theme trail is {bt:,} steps. Easy."),
            ("🗣️", "The Maddox Adda Loyalist", "Came to see the idol. Stayed four hours for the adda."),
            ("🧭", "The Planner", f"Knows {tp['name']} is quietest at {hours_range(tp['quiet_hours']['ashtami'])}. Has a meeting point. Already annoyed at you."),
        ]
        slides = [{"t": "cover", "theme": "red", "kicker": "Tag your gang 👇", "title": "Types of pandal hoppers",
                   "accent": "Which one are you?", "sub": "Eight kinds of people you'll meet in every pujo group.",
                   "bn": "আপনি কোন দলে? বন্ধুকে ট্যাগ করুন", "tag": "TAG A FRIEND 👇"}]
        for i, (icon, name, body) in enumerate(types):
            slides.append({"t": "tip", "theme": ["cream", "red", "dark"][i % 3], "icon": icon, "kicker": f"Type {i + 1} of {len(types)}",
                           "title": name, "body": body, "foot": "Tag this one 👇"})
        slides.append(self.cta(bn="কোনটা আপনি? কমেন্টে লিখুন · বন্ধুকে ট্যাগ করুন"))
        return self.carousel("types-of-pandal-hoppers", "Types of pandal hoppers (tag yours)", "2026-10-03", slides,
                             """Which pandal hopper are you? 😂🪔
The Ashtami Anjali Alarm, the Kabiraji Pilgrim, the Theme Critic, the North-Only Purist, the All-Nighter, the Step Counter, the Maddox Adda Loyalist… and the Planner (that's us).
Tag your gang and tell us your number in the comments 👇 Save it 📌 Plan your pujo free → link in bio.""",
                             """আপনি কোন ধরনের ঠাকুর-দেখিয়ে? 😂🪔
অষ্টমীর অঞ্জলির অ্যালার্ম, কবিরাজির তীর্থযাত্রী, থিম-সমালোচক, শুধু-উত্তর, সারা-রাত, স্টেপ-গোনা, ম্যাডক্সের আড্ডাবাজ… আর প্ল্যানার।
বন্ধুদের ট্যাগ করুন, কমেন্টে নম্বর লিখুন 👇 ফ্রি প্ল্যান → বায়োতে লিংক।""",
                             ["#PujoVibes", "#TagAFriend", "#Bangali"])

    def queue_hacks(self):
        q = hours_range(self.quiet_all)
        peak = hours_range(self.peak_hours)
        D = self.days
        rel = lambda did: round(100 * D[did]["factor"] / D["saptami"]["factor"])
        calmer = [("lake_town_adhibasi", "sreebhumi"), ("hindustan_park", "ekdalia"), ("sahajatri", "behala_notun_dal")]
        slides = [{"t": "cover", "theme": "red", "kicker": "Avoid the queue", "title": "7 hacks to beat the pujo crowd",
                   "accent": "Less queue, more thakur", "sub": "Backed by the crowd model in our free pujo app.",
                   "bn": "লাইন কম, ঠাকুর দেখা বেশি: ৭টা টিপস", "tag": "SAVE BEFORE SAPTAMI 📌"},
                  {"t": "tip", "theme": "cream", "icon": "🌅", "kicker": "Hack 1", "title": f"Go at {q}",
                   "body": "Every pandal in our guide is at its quietest at dawn, every puja day. Anjali, then thakur dekha."},
                  {"t": "tip", "theme": "red", "icon": "⏰", "kicker": "Hack 2", "title": f"Dodge {peak}",
                   "body": "That's when the whole city is out. Eat dinner then, and hop again after."},
                  {"t": "tip", "theme": "dark", "icon": "📊", "kicker": "Hack 3", "title": "Pick a lighter day",
                   "body": f"Panchami runs at about {rel('panchami')}% of Saptami's crowd and Shashthi {rel('shashthi')}%. Ashtami is the busiest at {rel('ashtami')}%."},
                  {"t": "tip", "theme": "red", "icon": "🚇", "kicker": "Hack 4", "title": "Metro, not car",
                   "body": "Cars are best avoided in North Kolkata, Central Kolkata and Lake Town. VIP Road jams for kilometres around Sreebhumi."},
                  {"t": "list", "theme": "cream", "kicker": "Hack 5", "title": "Visit the calmer neighbour",
                   "items": [{"icon": "🤫", "name": self.p[a]["name"], "bn": self.p[a].get("name_bn", ""),
                              "meta": f"Near {self.p[b]['name']}"} for a, b in calmer],
                   "note": "Fewer queues, and still worth the stop."},
                  {"t": "tip", "theme": "dark", "icon": "💡", "kicker": "Hack 6", "title": "Save lights for late night",
                   "body": f"{self.p['college_square']['name']}'s lights on the pond are best at {self.p['college_square']['best_slot_label']}. Do day pandals by day."},
                  {"t": "tip", "theme": "red", "icon": "📱", "kicker": "Hack 7", "title": "Check before you go",
                   "body": "Our free app shows each pandal's quiet hours and best time, plus live check-ins on puja days."},
                  self.cta()]
        return self.carousel("avoid-the-queue", "7 hacks to avoid the pujo queue", "2026-10-08", slides,
                             f"""Spend Saptami seeing thakur, not the back of someone's head 🪔
7 hacks: go at {q}, dodge {peak}, pick Panchami or Shashthi, take the metro, visit the calmer neighbour, save the light shows for late night, and check quiet hours before you leave.
Save this 📌 Quiet hours for 100+ pandals, free → link in bio.""",
                             f"""সপ্তমীতে লাইন নয়, ঠাকুর দেখুন 🪔
৭টা টিপস: ভোর {q}-এ যান, সন্ধে ৭টা থেকে রাত ১০টা এড়িয়ে চলুন, পঞ্চমী-ষষ্ঠী বেছে নিন, মেট্রো ধরুন, পাশের শান্ত পুজোয় যান, আলোর পুজো রাতে দেখুন।
সেভ করুন 📌 ১০০+ পুজোর কম ভিড়ের সময়, ফ্রি → বায়োতে লিংক।""",
                             ["#PujoTips", "#QuietHours", "#KolkataMetro"])

    def old_vs_new(self):
        old = sorted([p for p in self.g["pandals"] if p.get("est_year")], key=lambda p: p["est_year"])
        theme_ids = [("kumartuli_park", "Bold, artistic themes next to the idol-makers' quarter"),
                     ("tala_prattoy", "North Kolkata's blockbuster theme puja"),
                     ("suruchi_sangha", "Brings the art of a different Indian state each year"),
                     ("badamtala", "Usually built from unusual materials"),
                     ("bosepukur_sitala", "Famous for intricate material-based pandals"),
                     ("kashi_bose_lane", "A lane-side puja that keeps winning art awards"),
                     ("mudiali", "Thoughtful themes with an eco slant"),
                     ("66_pally", "A theme puja that often has a social message")]
        slides = [{"t": "cover", "theme": "red", "kicker": "Old school vs new wave", "title": "Heritage pujo or theme pujo?",
                   "accent": f"Since {old[0]['est_year']}", "sub": "The oldest pujas in our guide, the boldest theme pandals, and how to do both.",
                   "bn": "বনেদি না থিম? দুটোই দেখুন", "tag": "SAVE · WHICH TEAM ARE YOU? 📌"},
                  {"t": "tips", "theme": "cream", "kicker": "What's the difference?",
                   "items": [{"icon": "🏛️", "title": "Heritage & traditional", "body": "Ekchala idols, daker saaj, rituals kept the same way for generations. Bonedi bari pujas are in family homes."},
                             {"icon": "🎨", "title": "Theme", "body": "The whole pandal is an art installation. A new idea, material or craft every year."}]}]
        for i, part in enumerate(chunks(old, 3)):
            slides.append({"t": "list", "theme": "dark" if i % 2 else "red", "kicker": f"Heritage · oldest first · {i + 1}/3",
                           "title": ["Pujas with history", "Still going strong", "Classics of the city"][i],
                           "items": [{"badge": str(p["est_year"]), "name": p["name"], "bn": p.get("name_bn", ""),
                                      "meta": self.metro(p)} for p in part]})
        for i, part in enumerate(chunks(theme_ids, 4)):
            slides.append({"t": "list", "theme": "red" if i else "cream", "kicker": "Theme · art-led",
                           "title": "The theme heavyweights" if not i else "Made for the art lovers",
                           "items": [{"icon": "🎨", "name": self.p[pid]["name"], "meta": m}
                                     for pid, m in part]})
        nh = self.trails["north_heritage"]
        slides.append({"t": "tip", "theme": "dark", "icon": "🤝", "kicker": "Why choose?", "title": "Do both in one morning",
                       "body": f"Our {nh['name']} starts at {clock(nh['start_time'])} on {self.days[nh['day']]['name']}: Sovabazar Rajbari ({self.p['sovabazar_rajbari']['est_year']}), Bagbazar ({self.p['bagbazar']['est_year']}) and Kumartuli Park's theme, all on foot."})
        slides.append(self.cta(bn="আপনি কোন দলে — বনেদি না থিম? কমেন্টে লিখুন"))
        return self.carousel("heritage-vs-theme", "Old vs new: heritage pujas vs theme pujas", "2026-10-09", slides,
                             f"""Team Heritage or Team Theme? 🏛️🎨
From Sovabazar Rajbari ({self.p['sovabazar_rajbari']['est_year']}) and Bagbazar ({self.p['bagbazar']['est_year']}) to the art-led pandals of Kumartuli Park, Suruchi Sangha and Badamtala. Here's the oldest pujas in our guide and the theme heavyweights, and how to see both in one morning.
Comment your team 👇 Save it 📌 Plan free → link in bio.""",
                             f"""বনেদি না থিম? 🏛️🎨
শোভাবাজার রাজবাড়ি ({self.p['sovabazar_rajbari']['est_year']}), বাগবাজার ({self.p['bagbazar']['est_year']}) থেকে কুমোরটুলি পার্ক, সুরুচি সংঘ, বাদামতলার থিম। পুরনো পুজো আর থিমের সেরা, আর এক সকালে দুটোই দেখার রুট।
কমেন্টে লিখুন আপনি কোন দলে 👇 ফ্রি প্ল্যান → বায়োতে লিংক।""",
                             ["#BonediBari", "#ThemePujo", "#Heritage"])

    # ---------------------------------------------------------------- all
    def all(self):
        cs = [self.dates(), self.hoppers(), self.words_(), self.quiet_cheatsheet(), self.metro_sheet(),
              self.food_map(), self.queue_hacks(), self.survival(), self.old_vs_new()]
        cs += self.regions()
        cs += self.trails_all()
        cs.sort(key=lambda c: (c["date"], c["slug"]))
        for i, c in enumerate(cs, 1):
            c["id"] = f"{i:02d}-{c['slug']}"
            n = len(c["slides"])
            assert 6 <= n <= 10, (c["id"], n)
            assert c["slides"][0]["t"] == "cover" and c["slides"][-1]["t"] == "cta", c["id"]
            for j, s in enumerate(c["slides"], 1):
                s["page"], s["pages"] = j, n
                w = words(s)
                if w > MAX_WORDS:
                    print(f"warning: {c['id']} slide {j} has {w} words")
        return cs


def caption(c):
    return f"{c['caption_en']}\n\n{c['caption_bn']}\n\n{c['hashtags']}\n"


def build(out, g=None):
    g = g or json.loads((ROOT / "app" / "data" / "guide.json").read_text(encoding="utf-8"))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    cs = Carousels(g).all()
    spec = {"handle": HANDLE, "size": [1080, 1350], "carousels": cs}
    (out / "carousels.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# Pujo Parikrama 2026: Instagram carousels", "",
             f"{len(cs)} carousels for {HANDLE}. Slides are 1080×1350 JPEGs (`slide-01.jpg` …) in each folder; "
             "`caption.txt` has the English caption, the Bengali caption and the hashtags.", "",
             "| # | Carousel | Slides | Post on |", "|---|---|---|---|"]
    for c in cs:
        lines.append(f"| {c['id'][:2]} | [{c['title']}]({c['id']}/) | {len(c['slides'])} | {fmt_date(c['date'], True)} |")
    lines.append("")
    for c in cs:
        d = out / c["id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "caption.txt").write_text(caption(c), encoding="utf-8")
        lines += [f"## {c['id']}: {c['title']}", "",
                  f"**Slides:** {len(c['slides'])} · **Best posting date:** {fmt_date(c['date'], True)} 2026", "",
                  "```", caption(c).strip(), "```", ""]
    (out / "index.md").write_text("\n".join(lines), encoding="utf-8")
    return spec


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True, help="output folder")
    a = ap.parse_args(argv)
    spec = build(a.out)
    print(f"{len(spec['carousels'])} carousels, {sum(len(c['slides']) for c in spec['carousels'])} slides → {a.out}")


if __name__ == "__main__":
    main()
