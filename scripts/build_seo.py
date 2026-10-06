"""Crawlable, citable pages for search engines and AI answer engines (SEO / GEO / AEO).

The app itself is a JavaScript single-page app: Google renders it, but most AI crawlers (GPTBot,
ClaudeBot, PerplexityBot, …) read raw HTML only. This builds plain static HTML from app/data/guide.json:

    guide/                      the hub: dates, areas, top pandals, FAQ
    guide/dates/                Durga Puja 2026 day-by-day calendar with crowd levels
    guide/areas/<zone>/         each area: pandals, food, parking, how to get there
    guide/pandals/<id>/         every pandal: answer-first summary, facts, how to reach, FAQ
    guide/food/<id>/            every eatery: dishes, cost for two, hours, nearby pandals
    guide/trails/<id>/          the ready-made walking trails, stop by stop
    guide/parking/              park & ride and pay parking
    sitemap.xml, robots.txt, llms.txt, llms-full.txt
    index.html                  a static summary with links (between <!--seo:start--> and <!--seo:end-->),
                                which the app replaces once it boots

Every page has a canonical URL, a "last updated" date, a plain answer in the first paragraph, schema.org
JSON-LD (TouristAttraction + Event, Restaurant, FAQPage, BreadcrumbList, ItemList), and it says which
numbers are estimates. Stdlib only.

    python scripts/build_seo.py --out app        # deploy (deploy.yml); outputs are git-ignored
    python scripts/build_seo.py --out /tmp/seo   # anywhere else, for a look
"""
import argparse
import html
import json
import re
from datetime import date, datetime
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parent.parent
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


class Site:
    def __init__(self, g, base, out, verify=""):
        self.g, self.base, self.out = g, base.rstrip("/") + "/", Path(out)
        self.verify = f'<meta name="google-site-verification" content="{esc(verify)}">' if verify else ""
        self.meta = g["meta"]
        self.year = self.meta["year"]
        self.updated = datetime.fromisoformat(self.meta["generated_at"].replace("Z", "+00:00")).date().isoformat()
        self.days = {d["id"]: d for d in self.meta["days"]}
        self.zone = {z["id"]: z for z in g["zones"]}
        self.region = {r["id"]: r for r in g["regions"]}
        self.pandal = {p["id"]: p for p in g["pandals"]}
        self.food = {f["id"]: f for f in g["food"]}
        self.park = {p["id"]: p for p in g["parking"]}
        self.trail = {t["id"]: t for t in g["itineraries"]}
        self.pages = []   # (path, title, summary, priority)
        self.full = []    # markdown blocks for llms-full.txt
        self.start, self.end = self.days["panchami"]["date"], self.days["dashami"]["date"]

    # ------------------------------------------------------------------ helpers
    def url(self, path):
        return self.base + path

    def hour_crowd(self, p, day, h):
        hf = self.meta["model"]["hour_factors"]
        return min(100, round(p["crowd_base"] * 20 * self.days[day]["factor"] * hf[h]))

    def page(self, path, title, desc, body, *, ld=(), crumbs=(), priority=0.6, summary=None, app_link=""):
        """Write one page; `path` like 'guide/pandals/bagbazar/' (always a folder with index.html)."""
        depth = path.count("/")
        up = "../" * depth
        canonical = self.url(path)
        crumb_ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, "item": self.url(p)} for i, (n, p) in enumerate((("Pujo Parikrama", ""),) + tuple(crumbs))]}
        nav = " › ".join(f'<a href="{up}{p}">{esc(n)}</a>' for n, p in (("Home", ""),) + tuple(crumbs[:-1])) + (f" › <span>{esc(crumbs[-1][0])}</span>" if crumbs else "")
        cta = f'<a class="cta" href="{up}{app_link}">Open in the {NAME} app →</a>' if app_link is not None else ""
        doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canonical)}">{self.verify}
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{NAME} {self.year}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="{esc(self.url('icons/og.png'))}">
<meta property="article:modified_time" content="{self.updated}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{up}icons/icon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{up}guide/guide.css">
{jsonld(crumb_ld)}
{''.join(jsonld(x) for x in ld)}
</head>
<body>
<header class="top"><a class="brand" href="{up}guide/"><img src="{up}icons/icon-192.png" alt="" width="32" height="32"> {NAME} {self.year}</a><a class="open" href="{up}">Open app</a></header>
<main>
<nav class="crumbs" aria-label="Breadcrumb">{nav}</nav>
{body}
{cta}
<p class="updated">Last updated <time datetime="{self.updated}">{nice_date(self.updated, True)}</time>. {esc(self.meta['disclaimer'])} Crowd levels and best times are estimates from {NAME}'s crowd model (popularity, day and hour), not live counts. Cite as: “{NAME} {self.year}, {esc(canonical)}”.</p>
</main>
<footer><a href="{up}guide/">Durga Puja {self.year} guide</a> · <a href="{up}guide/dates/">Dates</a> · <a href="{up}guide/parking/">Parking</a> · <a href="{up}privacy.html">Privacy</a> · <a href="{up}llms.txt">llms.txt</a></footer>
</body>
</html>
"""
        f = self.out / path / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(doc, encoding="utf-8")
        self.pages.append((path, title, summary or desc, priority))

    def faq(self, qa):
        ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", "", a)}} for q, a in qa]}
        body = '<section class="faq"><h2>Frequently asked questions</h2>' + "".join(f"<h3>{esc(q)}</h3><p>{a}</p>" for q, a in qa) + "</section>"
        return body, ld

    def photos(self, items, alt):
        items = [p for p in (items or []) if p.get("src")][:4]
        if not items:
            return "", []
        figs = "".join(f'<figure><img loading="lazy" referrerpolicy="no-referrer" src="{esc(p["src"])}" alt="{esc(alt)}{" " + str(p["year"]) if p.get("year") else ""}" width="480" height="320">'
                       f'<figcaption>{esc(p.get("title", ""))} · <a href="{esc(p.get("page", ""))}" rel="nofollow">{esc(p.get("author", ""))}</a>, {esc(p.get("license", ""))}</figcaption></figure>' for p in items)
        return f'<div class="gallery">{figs}</div>', [p["src"] for p in items]

    def link_pandal(self, pid, up):
        p = self.pandal[pid]
        return f'<a href="{up}guide/pandals/{pid}/">{esc(p["name"])}</a>'

    def link_food(self, fid, up):
        return f'<a href="{up}guide/food/{fid}/">{esc(self.food[fid]["name"])}</a>'

    # ------------------------------------------------------------------ pandal
    def pandal_page(self, p):
        z = self.zone[p["zone"]]
        up = "../../../"
        m = p["nearest_metro"]
        quiet = p["quiet_hours"]
        known = ", ".join(TAGS.get(t, t) for t in p["tags"])
        est = f", established in {p['est_year']}" if p.get("est_year") else ""
        quiet_ash = hrange(quiet["ashtami"])
        lead = (f"<b>{esc(p['name'])}</b> ({esc(p.get('name_bn', ''))}) is a Durga Puja pandal in {esc(z['name'])}, Kolkata{est}. "
                f"{esc(p['highlight'])} In {self.year} the puja runs from Panchami, {nice_date(self.start)}, to Dashami, {nice_date(self.end)}. "
                f"Our crowd model suggests visiting {esc(p['best_slot_label'])}; on Ashtami, the busiest day, the quietest window is {quiet_ash}. "
                f"The nearest metro station is {esc(m['name'])} on the {LINE.get(m['line'], m['line'] + ' line')}, about {m['walk_min']} minutes' walk ({km(m['distance_m'])}). "
                f"Plan about {p['visit_min']} minutes inside.")
        foods = [x for x in p["food"] if x["id"] in self.food]
        parks = [x for x in p["parking"] if x["id"] in self.park]
        same = [q for q in z["pandal_ids"] if q != p["id"] and q in self.pandal][:8]
        rows = [("Area", f'<a href="{up}guide/areas/{z["id"]}/">{esc(z["name"])}</a> ({esc(self.region[z["region"]]["name"])} Kolkata)'),
                ("Known for", esc(known)),
                ("Established", esc(p["est_year"])) if p.get("est_year") else None,
                ("Popularity", f"{p['popularity']} out of 5"),
                ("Best time to visit", esc(p["best_slot_label"])),
                ("Time inside", f"about {p['visit_min']} minutes"),
                ("Nearest metro", f"{esc(m['name'])}, {LINE.get(m['line'], m['line'])} · {km(m['distance_m'])}, {m['walk_min']} min walk"),
                ("Buses", "; ".join(f"{esc(b['stop'])}: {esc(', '.join(b['routes']))} ({b['walk_min']} min walk)" for b in p.get("bus", []))) if p.get("bus") else None,
                ("Autos", "; ".join(esc(a["route"]) for a in p.get("auto", []))) if p.get("auto") else None,
                ("Coordinates", f"{p['lat']:.5f}, {p['lng']:.5f}" + (" (approximate)" if p.get("geo_source") == "osm-approx" else "")),
                ("Driving", esc(CAR.get(z.get("car_advisory"), ""))) if z.get("car_advisory") else None]
        facts = "<dl class='facts'>" + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in filter(None, rows)) + "</dl>"
        days_tbl = "<table class='days'><thead><tr><th>Day</th><th>Date</th><th>Quietest hours</th><th>At 8 pm</th></tr></thead><tbody>" + "".join(
            f"<tr><td>{esc(self.days[d]['name'])}</td><td>{nice_date(self.days[d]['date'])}</td><td>{hrange(quiet[d])}</td><td>{crowd_word(self.hour_crowd(p, d, 20))}</td></tr>" for d in MAIN_DAYS) + "</tbody></table>"
        food_html = "<ul>" + "".join(f"<li>{self.link_food(x['id'], up)}: {esc(', '.join(self.food[x['id']]['dishes'][:3]))} · {x['walk_min']} min walk</li>" for x in foods) + "</ul>" if foods else "<p>No eateries listed within walking distance.</p>"
        park_html = "<ul>" + "".join(f"<li>{esc(self.park[x['id']]['name'])} · {km(x['distance_m'])}, {x['walk_min']} min walk{(' · ' + esc(self.park[x['id']].get('rate_hint'))) if self.park[x['id']].get('rate_hint') else ''}</li>" for x in parks) + "</ul>" if parks else "<p>No parking listed nearby; come by metro.</p>"
        near_html = ", ".join(self.link_pandal(q, up) for q in same)
        gallery, imgs = self.photos(p.get("photos"), f"{p['name']} Durga Puja")
        qa = [
            (f"What is the best time to visit {p['name']}?", f"{esc(p['best_slot_label'])} is the best slot. On Saptami, Ashtami and Navami the quietest window is {hrange(quiet['saptami'])}; evenings from 6 pm to midnight are the busiest."),
            (f"How do I reach {p['name']} by metro?", f"Get off at {esc(m['name'])} ({LINE.get(m['line'], m['line'])}). It is about {km(m['distance_m'])} away, roughly {m['walk_min']} minutes on foot."),
            (f"Where can I park near {p['name']}?", (f"The nearest listed parking is {esc(self.park[parks[0]['id']]['name'])}, {km(parks[0]['distance_m'])} away. " if parks else "There is no listed parking nearby. ") + esc(CAR.get(z.get("car_advisory"), ""))),
            (f"What can I eat near {p['name']}?", ("Within walking distance: " + "; ".join(f"{esc(self.food[x['id']]['name'])} ({esc(', '.join(self.food[x['id']]['dishes'][:2]))})" for x in foods[:3]) + ".") if foods else "No eateries are listed within walking distance."),
            (f"When is Durga Puja {self.year} at {p['name']}?", f"From Panchami, {nice_date(self.start, True)}, to Dashami (Bijoya Dashami), {nice_date(self.end, True)}. Ashtami, the busiest day, is {nice_date(self.days['ashtami']['date'], True)}."),
        ]
        faq_html, faq_ld = self.faq(qa)
        body = f"""<article>
<h1>{esc(p['name'])} Durga Puja {self.year}: best time, how to reach, food nearby</h1>
<p class="lead">{lead}</p>
{gallery}
<h2>Key facts</h2>
{facts}
<h2>Crowds by day ({self.year})</h2>
{days_tbl}
<h2>Food nearby</h2>
{food_html}
<h2>Parking</h2>
{park_html}
{f'<h2>More pandals in {esc(z["name"])}</h2><p>{near_html}</p>' if near_html else ''}
{faq_html}
</article>"""
        place = {"@context": "https://schema.org", "@type": "TouristAttraction", "@id": self.url(f"guide/pandals/{p['id']}/#place"), "name": p["name"],
                 "alternateName": p.get("name_bn"), "description": p["highlight"], "url": self.url(f"guide/pandals/{p['id']}/"),
                 "geo": {"@type": "GeoCoordinates", "latitude": p["lat"], "longitude": p["lng"]},
                 "address": {"@type": "PostalAddress", "addressLocality": "Kolkata", "addressRegion": "West Bengal", "addressCountry": "IN"},
                 "containedInPlace": {"@type": "Place", "name": f"{z['name']}, Kolkata"}, "isAccessibleForFree": True, "touristType": "Durga Puja pandal hopping"}
        if imgs:
            place["image"] = imgs
        event = {"@context": "https://schema.org", "@type": "Event", "name": f"Durga Puja {self.year} at {p['name']}", "startDate": self.start, "endDate": self.end,
                 "eventStatus": "https://schema.org/EventScheduled", "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode", "isAccessibleForFree": True,
                 "description": f"Durga Puja at {p['name']}, {z['name']}, Kolkata. {p['highlight']}", "location": {"@id": self.url(f"guide/pandals/{p['id']}/#place"), "@type": "Place", "name": p["name"],
                 "address": place["address"], "geo": place["geo"]}}
        if imgs:
            event["image"] = imgs
        desc = f"{p['name']}, {z['name']}: best time to visit ({p['best_slot_label']}), quiet hours, nearest metro ({m['name']}), food and parking for Durga Puja {self.year}."
        self.page(f"guide/pandals/{p['id']}/", f"{p['name']} Durga Puja {self.year}: timings, best time, how to reach | {NAME}", desc, body,
                  ld=(place, event, faq_ld), crumbs=(("Durga Puja guide", "guide/"), (z["name"], f"guide/areas/{z['id']}/"), (p["name"], f"guide/pandals/{p['id']}/")),
                  priority=0.8 if p["popularity"] >= 4 else 0.6, summary=re.sub(r"<[^>]+>", "", lead), app_link=f"#p={p['id']}")
        self.full.append(f"### {p['name']} ({z['name']})\n{re.sub(r'<[^>]+>', '', lead)}\nKnown for: {known}. Food nearby: {', '.join(self.food[x['id']]['name'] for x in foods) or 'none listed'}. Page: {self.url('guide/pandals/' + p['id'] + '/')}\n")

    # ------------------------------------------------------------------ food
    def food_page(self, f):
        z = self.zone[f["zone"]]
        up = "../../../"
        m = f.get("nearest_metro")
        c2 = cost2(f)
        hours = f.get("hours")
        h = re.match(r"^(\d\d:\d\d)-(\d\d:\d\d)$", hours or "")
        diet = {"veg": "pure vegetarian", "nonveg": "non-vegetarian", "both": "vegetarian and non-vegetarian"}[f["veg"]]
        near = [q for q in f.get("near_pandals", []) if q in self.pandal]
        lead = (f"<b>{esc(f['name'])}</b> is a {FOOD_TYPE.get(f['type'], 'place to eat')} in {esc(z['name'])}, Kolkata, known for {esc(', '.join(f['dishes']))}. "
                f"Expect about {rupees(c2)} for two{'' if f.get('cost2') else ' (estimate)'}. It serves {diet} food"
                + (f" and is open {clock(h.group(1))} to {clock(h.group(2))}" if h else "") + ". "
                + (f"{esc(f['note'])} " if f.get("note") else "")
                + (f"It is within walking distance of {', '.join(esc(self.pandal[q]['name']) for q in near[:3])}." if near else ""))
        rows = [("Area", f'<a href="{up}guide/areas/{z["id"]}/">{esc(z["name"])}</a>'), ("Type", esc(FOOD_TYPE.get(f["type"], f["type"]))),
                ("Must try", esc(", ".join(f["dishes"]))), ("Cost for two", rupees(c2) + ("" if f.get("cost2") else " (estimate)")),
                ("Food", diet), ("Hours", f"{clock(h.group(1))} – {clock(h.group(2))} (puja timings can differ)" if h else None),
                ("Nearest metro", f"{esc(m['name'])} · {km(m['distance_m'])}, {m['walk_min']} min walk") if m else None]
        facts = "<dl class='facts'>" + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows if v) + "</dl>"
        near_html = "<ul>" + "".join(f"<li>{self.link_pandal(q, up)}</li>" for q in near) + "</ul>" if near else "<p>None listed.</p>"
        gallery, imgs = self.photos(f.get("photos"), f"{f['name']} food")
        qa = [(f"What should I eat at {f['name']}?", esc(", ".join(f["dishes"])) + "."),
              (f"How much does {f['name']} cost for two?", f"About {rupees(c2)}{'' if f.get('cost2') else ', estimated from the type of place and its price range'}."),
              (f"Is {f['name']} vegetarian?", {"veg": "Yes, it is pure vegetarian.", "nonveg": "No, it serves non-vegetarian food.", "both": "It serves both vegetarian and non-vegetarian food."}[f["veg"]])]
        if h:
            qa.append((f"What are {f['name']}'s timings?", f"Usually {clock(h.group(1))} to {clock(h.group(2))}. During the puja, timings can change, so check locally."))
        if near:
            qa.append((f"Which pandals are near {f['name']}?", ", ".join(esc(self.pandal[q]["name"]) for q in near[:5]) + "."))
        faq_html, faq_ld = self.faq(qa)
        body = f"""<article>
<h1>{esc(f['name'])}, Kolkata: what to eat, cost for two, timings</h1>
<p class="lead">{lead}</p>
{gallery}
<h2>Key facts</h2>
{facts}
<h2>Pandals within walking distance</h2>
{near_html}
{faq_html}
</article>"""
        rest = {"@context": "https://schema.org", "@type": "Restaurant" if f["type"] in ("restaurant", "cabin") else "FoodEstablishment", "name": f["name"],
                "url": self.url(f"guide/food/{f['id']}/"), "servesCuisine": ["Bengali", "Indian"], "priceRange": "₹" * min(max(f.get("price") or 2, 1), 3),
                "geo": {"@type": "GeoCoordinates", "latitude": f["lat"], "longitude": f["lng"]},
                "address": {"@type": "PostalAddress", "addressLocality": "Kolkata", "addressRegion": "West Bengal", "addressCountry": "IN"},
                "description": f"{FOOD_TYPE.get(f['type'], 'Eatery')} in {z['name']}, known for {', '.join(f['dishes'])}."}
        if h:
            rest["openingHours"] = f"Mo-Su {h.group(1)}-{h.group(2)}"
        if f["veg"] == "veg":
            rest["suitableForDiet"] = "https://schema.org/VegetarianDiet"
        if imgs:
            rest["image"] = imgs
        desc = f"{f['name']} ({z['name']}, Kolkata): {', '.join(f['dishes'][:3])}. About {rupees(c2)} for two; pandals nearby for Durga Puja {self.year}."
        self.page(f"guide/food/{f['id']}/", f"{f['name']}, Kolkata: menu highlights, cost for two, timings | {NAME}", desc, body,
                  ld=(rest, faq_ld), crumbs=(("Durga Puja guide", "guide/"), (z["name"], f"guide/areas/{z['id']}/"), (f["name"], f"guide/food/{f['id']}/")),
                  priority=0.5, summary=re.sub(r"<[^>]+>", "", lead), app_link=f"#p={f['id']}")
        self.full.append(f"### {f['name']} ({z['name']}): eatery\n{re.sub(r'<[^>]+>', '', lead)}\nPage: {self.url('guide/food/' + f['id'] + '/')}\n")

    # ------------------------------------------------------------------ area
    def area_page(self, z):
        up = "../../../"
        ps = sorted((self.pandal[i] for i in z["pandal_ids"] if i in self.pandal), key=lambda p: -p["popularity"])
        fs = [self.food[i] for i in z.get("food_ids", []) if i in self.food] or [f for f in self.g["food"] if f["zone"] == z["id"]]
        pk = [self.park[i] for i in z.get("parking_ids", []) if i in self.park]
        top = ", ".join(p["name"] for p in ps[:4])
        lead = (f"<b>{esc(z['name'])}</b> ({esc(z.get('name_bn', ''))}) is one of Kolkata's Durga Puja pandal-hopping areas, in {esc(self.region[z['region']]['name'])} Kolkata. "
                f"{esc(z.get('vibe', ''))} This guide lists {len(ps)} pandals here, including {esc(top)}. {esc(z.get('walk_tip', ''))}")
        lst = "<ol class='list'>" + "".join(f"<li>{self.link_pandal(p['id'], up)}: {esc(p['highlight'])} <small>Best: {esc(p['best_slot_label'])} · metro {esc(p['nearest_metro']['name'])}</small></li>" for p in ps) + "</ol>"
        food = "<ul>" + "".join(f"<li>{self.link_food(f['id'], up)}: {esc(', '.join(f['dishes'][:3]))} · {rupees(cost2(f))} for two</li>" for f in fs) + "</ul>" if fs else "<p>None listed.</p>"
        park = "<ul>" + "".join(f"<li>{esc(x['name'])}{(' · ' + esc(x['rate_hint'])) if x.get('rate_hint') else ''}{(': ' + esc(x['note'])) if x.get('note') else ''}</li>" for x in pk) + "</ul>" if pk else "<p>No parking listed; come by metro.</p>"
        qa = [(f"Which are the best pandals in {z['name']}?", esc(", ".join(p["name"] for p in ps[:6])) + "."),
              (f"How do I get to {z['name']} for pandal hopping?", esc(z.get("walk_tip", "")) or "Take the metro to the nearest station and walk."),
              (f"Can I drive to {z['name']} during Durga Puja?", esc(CAR.get(z.get("car_advisory"), "Check local traffic advisories.")))]
        faq_html, faq_ld = self.faq(qa)
        items = {"@context": "https://schema.org", "@type": "ItemList", "name": f"Durga Puja pandals in {z['name']}, Kolkata", "numberOfItems": len(ps),
                 "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": self.url(f"guide/pandals/{p['id']}/"), "name": p["name"]} for i, p in enumerate(ps)]}
        body = f"""<article>
<h1>Durga Puja pandals in {esc(z['name'])} {self.year}: map-free list, food and parking</h1>
<p class="lead">{lead}</p>
<h2>Pandals ({len(ps)})</h2>
{lst}
<h2>Food</h2>
{food}
<h2>Parking</h2>
{park}
{faq_html}
</article>"""
        self.page(f"guide/areas/{z['id']}/", f"Durga Puja {self.year} pandals in {z['name']}, Kolkata | {NAME}",
                  f"{len(ps)} Durga Puja pandals in {z['name']}, Kolkata, with best times, metro, food and parking for {self.year}.", body,
                  ld=(items, faq_ld), crumbs=(("Durga Puja guide", "guide/"), (z["name"], f"guide/areas/{z['id']}/")), priority=0.8,
                  summary=re.sub(r"<[^>]+>", "", lead), app_link="#explore")
        self.full.append(f"## Area: {z['name']}\n{re.sub(r'<[^>]+>', '', lead)}\nPage: {self.url('guide/areas/' + z['id'] + '/')}\n")

    # ------------------------------------------------------------------ trail
    def trail_page(self, t):
        up = "../../../"
        d = self.days.get(t.get("day"), {})
        tot = t["totals"]
        stops = [s for seg in t["segments"] for s in seg.get("stops", []) if s.get("pandal") in self.pandal]
        lead = (f"<b>{esc(t['name'])}</b> is a ready-made Durga Puja {self.year} pandal-hopping route: {esc(t['blurb'])} "
                f"It covers {len(stops)} pandals in about {tot['duration_min'] // 60} h {tot['duration_min'] % 60} min, "
                f"with {tot['walk_km']} km on foot (about {tot['steps']:,} steps), starting {clock(t['start_time'])} on {esc(d.get('name', ''))} ({nice_date(d['date']) if d else ''}).")
        ol = "<ol class='list'>" + "".join(f"<li><b>{s.get('arrive', '')}</b> {self.link_pandal(s['pandal'], up)}: {s.get('walk_min', 0)} min walk, {s.get('dwell_min', 0)} min inside, {crowd_word(s.get('crowd', 0))}</li>" for s in stops) + "</ol>"
        ld = {"@context": "https://schema.org", "@type": "TouristTrip", "name": t["name"], "description": t["blurb"], "touristType": "Durga Puja pandal hopping",
              "itinerary": {"@type": "ItemList", "numberOfItems": len(stops), "itemListElement": [
                  {"@type": "ListItem", "position": i + 1, "item": {"@type": "TouristAttraction", "name": self.pandal[s["pandal"]]["name"], "url": self.url(f"guide/pandals/{s['pandal']}/")}} for i, s in enumerate(stops)]}}
        body = f"""<article>
<h1>{esc(t['name'])}: Durga Puja {self.year} pandal-hopping route</h1>
<p class="lead">{lead}</p>
<h2>Stops</h2>
{ol}
</article>"""
        self.page(f"guide/trails/{t['id']}/", f"{t['name']}: Durga Puja {self.year} pandal hopping route | {NAME}",
                  f"{t['name']}: {len(stops)} pandals, {tot['walk_km']} km, start {clock(t['start_time'])}. {t['blurb']}", body,
                  ld=(ld,), crumbs=(("Durga Puja guide", "guide/"), (t["name"], f"guide/trails/{t['id']}/")), priority=0.7,
                  summary=re.sub(r"<[^>]+>", "", lead), app_link=f"#trail={t['id']}")
        self.full.append(f"## Trail: {t['name']}\n{re.sub(r'<[^>]+>', '', lead)}\nStops: {', '.join(self.pandal[s['pandal']]['name'] for s in stops)}. Page: {self.url('guide/trails/' + t['id'] + '/')}\n")

    # ------------------------------------------------------------------ dates, parking, hub
    def dates_page(self):
        rows = "".join(f"<tr><td>{esc(d['name'])} ({esc(d['name_bn'])})</td><td>{nice_date(d['date'], True)}</td><td>{'' if d['id'] == 'mahalaya' else crowd_word(d['factor'] * 70)}</td></tr>" for d in self.meta["days"])
        a = self.days["ashtami"]
        lead = (f"Durga Puja {self.year} in Kolkata runs from <b>Panchami, {nice_date(self.start, True)}</b>, to <b>Bijoya Dashami, {nice_date(self.end, True)}</b>. "
                f"Mahalaya, which opens Debi Paksha, falls on {nice_date(self.days['mahalaya']['date'], True)}. The main days are Saptami ({nice_date(self.days['saptami']['date'])}), "
                f"Ashtami ({nice_date(a['date'])}) and Navami ({nice_date(self.days['navami']['date'])}); Ashtami is usually the most crowded.")
        qa = [(f"When is Durga Puja {self.year}?", re.sub(r"<[^>]+>", "", lead)),
              (f"Which day of Durga Puja {self.year} is the most crowded?", f"Ashtami, {nice_date(a['date'], True)}, followed by Saptami and Navami."),
              ("What is the best time of day for pandal hopping?", "Early morning, from about 5 am to 9 am, is the quietest. Crowds build from late afternoon and peak between 7 pm and midnight."),
              (f"When is Mahalaya {self.year}?", f"{nice_date(self.days['mahalaya']['date'], True)}.")]
        faq_html, faq_ld = self.faq(qa)
        ev = {"@context": "https://schema.org", "@type": "Event", "name": f"Durga Puja {self.year}, Kolkata", "startDate": self.start, "endDate": self.end,
              "eventStatus": "https://schema.org/EventScheduled", "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode", "isAccessibleForFree": True,
              "location": {"@type": "Place", "name": "Kolkata", "address": {"@type": "PostalAddress", "addressLocality": "Kolkata", "addressRegion": "West Bengal", "addressCountry": "IN"}},
              "description": f"Durga Puja in Kolkata, {self.year}: Panchami to Bijoya Dashami. UNESCO lists Durga Puja in Kolkata as Intangible Cultural Heritage."}
        body = f"""<article>
<h1>Durga Puja {self.year} dates in Kolkata: Mahalaya to Dashami</h1>
<p class="lead">{lead}</p>
<table class="days"><thead><tr><th>Day</th><th>Date</th><th>Crowds</th></tr></thead><tbody>{rows}</tbody></table>
{faq_html}
</article>"""
        self.page("guide/dates/", f"Durga Puja {self.year} dates: Mahalaya, Saptami, Ashtami, Navami, Dashami | {NAME}",
                  f"Durga Puja {self.year} in Kolkata: Panchami {nice_date(self.start)} to Dashami {nice_date(self.end)}; Ashtami {nice_date(a['date'])}. Day-by-day crowd guide.",
                  body, ld=(ev, faq_ld), crumbs=(("Durga Puja guide", "guide/"), ("Dates", "guide/dates/")), priority=0.9, summary=re.sub(r"<[^>]+>", "", lead), app_link="")
        self.full.append(f"## Dates\n{re.sub(r'<[^>]+>', '', lead)}\n")

    def parking_page(self):
        rows = "".join(f"<li><b>{esc(x['name'])}</b> ({esc(self.zone[x['zone']]['name'])}){(' · ' + esc(x['rate_hint'])) if x.get('rate_hint') else ''}{(': ' + esc(x['note'])) if x.get('note') else ''}</li>" for x in self.g["parking"])
        lead = (f"During Durga Puja {self.year}, many Kolkata lanes close to cars in the evenings. The easiest plan is to park at a metro park-and-ride and ride in. "
                f"This page lists {len(self.g['parking'])} park-and-ride and pay-parking spots.")
        body = f"<article><h1>Durga Puja {self.year} parking in Kolkata: park and ride</h1><p class='lead'>{lead}</p><ul class='list'>{rows}</ul></article>"
        self.page("guide/parking/", f"Durga Puja {self.year} parking in Kolkata: park & ride, pay parking | {NAME}",
                  f"Where to park for Durga Puja {self.year} in Kolkata: {len(self.g['parking'])} park-and-ride and pay-parking spots, with rates.", body,
                  crumbs=(("Durga Puja guide", "guide/"), ("Parking", "guide/parking/")), priority=0.7, summary=lead, app_link="#explore")
        self.full.append(f"## Parking\n{lead}\n" + "\n".join(f"- {x['name']} ({self.zone[x['zone']]['name']}){': ' + x['rate_hint'] if x.get('rate_hint') else ''}" for x in self.g["parking"]) + "\n")

    def hub_page(self):
        up = "../"
        top = sorted(self.g["pandals"], key=lambda p: (-p["popularity"], -p["crowd_base"]))[:12]
        lead = (f"<b>{NAME}</b> is a free guide to Durga Puja {self.year} in Kolkata. It covers {len(self.g['pandals'])} pandals across {len(self.g['zones'])} areas, "
                f"{len(self.g['food'])} places to eat and {len(self.g['parking'])} parking spots, with the best time to visit each pandal, the nearest metro station, "
                f"buses, ready-made walking trails and a step tracker. The puja runs from Panchami, {nice_date(self.start, True)}, to Dashami, {nice_date(self.end, True)}.")
        areas = "<ul class='cols'>" + "".join(f"<li><a href='{up}guide/areas/{z['id']}/'>{esc(z['name'])}</a> <small>{len(z['pandal_ids'])} pandals</small></li>" for z in self.g["zones"]) + "</ul>"
        tops = "<ol class='list'>" + "".join(f"<li>{self.link_pandal(p['id'], up)} <small>({esc(self.zone[p['zone']]['name'])})</small>: {esc(p['highlight'])}</li>" for p in top) + "</ol>"
        trails = "<ul>" + "".join(f"<li><a href='{up}guide/trails/{t['id']}/'>{esc(t['name'])}</a>: {esc(t['blurb'])}</li>" for t in self.g["itineraries"]) + "</ul>"
        qa = [(f"When is Durga Puja {self.year} in Kolkata?", f"Panchami {nice_date(self.start, True)} to Bijoya Dashami {nice_date(self.end, True)}. Mahalaya is {nice_date(self.days['mahalaya']['date'], True)}. See the <a href='{up}guide/dates/'>day-by-day dates</a>."),
              ("Which are the most famous Durga Puja pandals in Kolkata?", ", ".join(esc(p["name"]) for p in top[:8]) + "."),
              ("What is the best time to go pandal hopping in Kolkata?", "Early morning (5–9 am) and after 1 am are the quietest. Evenings from 6 pm to midnight are the busiest, especially on Ashtami."),
              ("How do I get around Kolkata during Durga Puja?", "The metro is the fastest way. Many neighbourhood lanes close to cars in the evening, so park at a park-and-ride and walk the last stretch. Each pandal page lists its nearest metro station and walking time."),
              ("Which areas of Kolkata are best for pandal hopping?", "North Kolkata (Kumartuli, Bagbazar, Hatibagan) for heritage and bonedi bari pujas; South Kolkata (Gariahat, Ballygunge, Lake Market, Behala) for theme pandals; Salt Lake and Lake Town for big-budget installations."),
              (f"Is {NAME} free?", "Yes. It works in the browser, in English, Bengali and Hindi, and most of it works offline.")]
        faq_html, faq_ld = self.faq(qa)
        web = {"@context": "https://schema.org", "@type": "WebSite", "name": NAME, "url": self.base, "inLanguage": ["en", "bn", "hi"],
               "description": f"Kolkata Durga Puja {self.year} pandal-hopping guide."}
        app = {"@context": "https://schema.org", "@type": "WebApplication", "name": f"{NAME} {self.year}", "url": self.base, "applicationCategory": "TravelApplication",
               "operatingSystem": "Any (web browser)", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "INR"}, "inLanguage": ["en", "bn", "hi"]}
        body = f"""<article>
<h1>Kolkata Durga Puja {self.year} guide: pandals, dates, food, routes</h1>
<p class="lead">{lead}</p>
<h2>Areas</h2>
{areas}
<h2>Most-visited pandals</h2>
{tops}
<h2>Ready-made trails</h2>
{trails}
<p><a href="{up}guide/dates/">Durga Puja {self.year} dates</a> · <a href="{up}guide/parking/">Parking</a></p>
{faq_html}
</article>"""
        self.page("guide/", f"Kolkata Durga Puja {self.year} guide: {len(self.g['pandals'])} pandals, dates, food, routes | {NAME}",
                  f"Free Kolkata Durga Puja {self.year} guide: {len(self.g['pandals'])} pandals by area with best times and metro, dates, food, parking and walking trails.",
                  body, ld=(web, app, faq_ld), crumbs=(("Durga Puja guide", "guide/"),), priority=1.0, summary=re.sub(r"<[^>]+>", "", lead), app_link="")
        self.hub_lead = re.sub(r"<[^>]+>", "", lead)

    # ------------------------------------------------------------------ files for crawlers
    def write_root_files(self):
        o = self.out
        urls = [("", 1.0)] + [(p, pr) for p, _, _, pr in self.pages]
        sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        sm += [f"<url><loc>{xml_escape(self.url(p))}</loc><lastmod>{self.updated}</lastmod><priority>{pr:.1f}</priority></url>" for p, pr in urls]
        sm.append("</urlset>")
        (o / "sitemap.xml").write_text("\n".join(sm) + "\n", encoding="utf-8")
        (o / "robots.txt").write_text(
            "# Everyone is welcome, search engines and AI crawlers alike: the guide is meant to be found and cited.\n"
            "User-agent: *\nAllow: /\nDisallow: /kit/\n\n"
            "User-agent: GPTBot\nAllow: /\n\nUser-agent: OAI-SearchBot\nAllow: /\n\nUser-agent: ChatGPT-User\nAllow: /\n\n"
            "User-agent: ClaudeBot\nAllow: /\n\nUser-agent: Claude-SearchBot\nAllow: /\n\nUser-agent: Claude-User\nAllow: /\n\n"
            "User-agent: PerplexityBot\nAllow: /\n\nUser-agent: Google-Extended\nAllow: /\n\nUser-agent: Applebot-Extended\nAllow: /\n\n"
            f"Sitemap: {self.url('sitemap.xml')}\n", encoding="utf-8")
        pandal_links = "\n".join(f"- [{p['name']}]({self.url('guide/pandals/' + p['id'] + '/')}): {self.zone[p['zone']]['name']}. {p['highlight']}"
                                 for p in sorted(self.g["pandals"], key=lambda p: -p["popularity"]))
        llms = f"""# {NAME}: Kolkata Durga Puja {self.year} guide

> {self.hub_lead}

Facts here come from a curated dataset updated {self.updated}. Crowd levels and best times are model estimates (popularity × day × hour), not live counts. Cite as "{NAME} {self.year}" with the page link.

## Key pages
- [Kolkata Durga Puja {self.year} guide]({self.url('guide/')}): areas, most-visited pandals, trails, FAQ
- [Durga Puja {self.year} dates]({self.url('guide/dates/')}): Mahalaya {nice_date(self.days['mahalaya']['date'], True)}; Panchami {nice_date(self.start, True)} to Dashami {nice_date(self.end, True)}
- [Parking and park & ride]({self.url('guide/parking/')})
- [Full text for LLMs]({self.url('llms-full.txt')}): every pandal, eatery and trail in one file
- [Open data (JSON)]({self.url('data/guide.json')}): the dataset behind the app

## Areas
""" + "\n".join(f"- [{z['name']}]({self.url('guide/areas/' + z['id'] + '/')}): {z.get('vibe', '')}" for z in self.g["zones"]) + """

## Trails
""" + "\n".join(f"- [{t['name']}]({self.url('guide/trails/' + t['id'] + '/')}): {t['blurb']}" for t in self.g["itineraries"]) + f"""

## Pandals
{pandal_links}

## Optional
- [The app]({self.base}): live check-ins, route planner, step tracker (JavaScript)
- [Privacy policy]({self.url('privacy.html')})
"""
        (o / "llms.txt").write_text(llms, encoding="utf-8")
        full = f"# {NAME}: Kolkata Durga Puja {self.year}, full guide\n\n{self.hub_lead}\n\nUpdated {self.updated}. {self.meta['disclaimer']} Crowd levels are model estimates.\n\n" + "\n".join(self.full)
        (o / "llms-full.txt").write_text(full, encoding="utf-8")

    def write_index_block(self):
        """A plain-HTML summary in app/index.html, for crawlers that don't run JavaScript. The app removes it on boot."""
        idx = self.out / "index.html"
        if not idx.exists():
            return
        s = idx.read_text(encoding="utf-8")
        a, b = "<!--seo:start-->", "<!--seo:end-->"
        if a not in s:
            return
        areas = " · ".join(f'<a href="guide/areas/{z["id"]}/">{esc(z["name"])}</a>' for z in self.g["zones"])
        top = " · ".join(f'<a href="guide/pandals/{p["id"]}/">{esc(p["name"])}</a>' for p in sorted(self.g["pandals"], key=lambda p: -p["popularity"])[:16])
        block = (f'{a}<section id="seo-static" class="seo-static"><h1>Kolkata Durga Puja {self.year} guide</h1><p>{esc(self.hub_lead)}</p>'
                 f'<p><a href="guide/">Read the full guide</a> · <a href="guide/dates/">Durga Puja {self.year} dates</a> · <a href="guide/parking/">Parking</a></p>'
                 f'<h2>Areas</h2><p>{areas}</p><h2>Popular pandals</h2><p>{top}</p></section>{jsonld(self.site_ld())}{b}')
        s = s[:s.index(a)] + block + s[s.index(b) + len(b):]
        s = re.sub(r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{self.base}">' + self.verify, s, count=1)
        idx.write_text(s, encoding="utf-8")

    def site_ld(self):
        return {"@context": "https://schema.org", "@graph": [
            {"@type": "WebSite", "@id": self.base + "#site", "name": NAME, "url": self.base, "inLanguage": ["en", "bn", "hi"],
             "description": f"Kolkata Durga Puja {self.year} pandal-hopping guide."},
            {"@type": "WebApplication", "name": f"{NAME} {self.year}", "url": self.base, "applicationCategory": "TravelApplication",
             "operatingSystem": "Any (web browser)", "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "INR"},
             "inLanguage": ["en", "bn", "hi"], "description": self.hub_lead}]}

    def build(self):
        for p in self.g["pandals"]:
            self.pandal_page(p)
        for f in self.g["food"]:
            self.food_page(f)
        for z in self.g["zones"]:
            self.area_page(z)
        for t in self.g["itineraries"]:
            self.trail_page(t)
        self.dates_page()
        self.parking_page()
        self.hub_page()
        css = ROOT / "scripts" / "seo" / "guide.css"
        (self.out / "guide" / "guide.css").write_text(css.read_text(encoding="utf-8"), encoding="utf-8")
        self.write_root_files()
        self.write_index_block()
        return len(self.pages)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "app"))
    ap.add_argument("--guide", default=str(ROOT / "app" / "data" / "guide.json"))
    a = ap.parse_args()
    g = json.loads(Path(a.guide).read_text(encoding="utf-8"))
    site = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
    n = Site(g, site["url"], a.out, site.get("google_site_verification", "")).build()
    print(f"{n} pages + sitemap.xml, robots.txt, llms.txt, llms-full.txt → {a.out}")


if __name__ == "__main__":
    main()
