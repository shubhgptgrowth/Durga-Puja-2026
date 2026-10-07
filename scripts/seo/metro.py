"""Durga Puja by metro: /guide/metro/ (every pandal under its nearest station, plus the Metro's puja announcements)
and /guide/metro/<station>/ for each station with two or more pandals within a 20-minute walk, for searches like
"durga puja pandals near girish park metro". Announcements come from data/raw/metro_2026.toml."""
import re
import tomllib
from datetime import date
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

from .common import LINE, crowd_word, esc, hrange, km, nice_date
from .knowledge import share_bar

ROOT = Path(__file__).resolve().parents[2]
NOTICES = ROOT / "data" / "raw" / "metro_2026.toml"
NEAR_MIN = 20       # a station page lists pandals within this walk
MIN_PANDALS = 2     # …and exists only when it has at least this many
FAR_MIN = 30        # beyond this, a pandal has "no metro within walking distance"
LINES = {**LINE, "suburban": "suburban railway"}
LINE_ORDER = ["blue", "green", "purple", "orange", "suburban"]


def walk(a, b):
    """Metres and minutes on foot between two (lat, lng) pairs, as pipeline/enrich.py computes them
    (straight line × 1.3 for the lanes, at a 3.2 km/h festival-crowd pace)."""
    lat1, lng1, lat2, lng2 = map(radians, (*a, *b))
    m = 2 * 6_371_000 * asin(sqrt(sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2))
    return round(m), round(m * 1.3 / (3.2 * 1000 / 60))


def station_label(s):
    """'Girish Park metro station', or 'Ballygunge Junction railway station' for the suburban line."""
    name = re.sub(r"\s*\((Suburban)\)", "", s["name"])
    return f"{name} railway station" if s["line"] == "suburban" else f"{name} metro station"


def day_month(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} {d:%B}"


def short_name(s):
    return re.sub(r"\s*\(.*\)", "", s["name"])


def metro_stations(g):
    """[(station, [(minutes, metres, pandal), …nearest first])] for every station that gets its own page."""
    out = []
    for s in g["transit"]:
        near = sorted(((w, m, p) for p in g["pandals"] for m, w in [walk((s["lat"], s["lng"]), (p["lat"], p["lng"]))] if w <= NEAR_MIN),
                      key=lambda x: (x[0], x[2]["name"]))
        if len(near) >= MIN_PANDALS:
            out.append((s, near))
    return out


def load_notices():
    if not NOTICES.exists():
        return {"puja_nights": {"announced": False}, "notice": []}
    return tomllib.loads(NOTICES.read_text(encoding="utf-8"))


class MetroMixin:
    def metro_prepare(self):
        """Before the pandal pages, so they can link to their station's page."""
        self.metro = metro_stations(self.g)
        self.metro_page = {s["id"] for s, _ in self.metro}
        self.station = {s["id"]: s for s in self.g["transit"]}
        self.notices = load_notices()

    def metro_far(self, p):
        return p["nearest_metro"]["walk_min"] > FAR_MIN

    def link_station(self, sid, up, text=None):
        s = self.station.get(sid)
        name = esc(text or (short_name(s) if s else sid))
        return f'<a href="{up}guide/metro/{sid}/">{name}</a>' if sid in self.metro_page else name

    def nights_answer(self, up=""):
        n = self.notices.get("puja_nights", {})
        if n.get("announced") and n.get("text"):
            src = f" <small>(<a href='{esc(n['source'])}' rel='noopener'>source</a>)</small>" if n.get("source") else ""
            return esc(n["text"]) + src
        return (f"Metro Railway hasn't announced its puja-night timings for {self.year} yet (as of {day_month(self.updated)}). In recent years the Blue Line "
                f"ran late into the night from Saptami to Navami, but check the official announcement before you plan a late return. "
                f"We add it to <a href='{up}guide/metro/'>this page</a> the day it's announced.")

    def notices_html(self, up):
        items = "".join(
            f"<li><b>{esc(x['title'])}</b> <small>(announced {day_month(x['date'])})</small>: {esc(x['text'])}"
            + (f" <small><a href='{esc(x['source'])}' rel='noopener'>Source</a></small>" if x.get("source") else "") + "</li>"
            for x in sorted(self.notices.get("notice", []), key=lambda x: x["date"], reverse=True))
        return (f"<h2>Metro timings for Durga Puja {self.year}</h2><p>{self.nights_answer(up)}</p>"
                + (f"<ul>{items}</ul>" if items else ""))

    def metro_pages(self):
        for s, near in self.metro:
            self.station_page(s, near)
        self.metro_hub()

    def station_page(self, s, near):
        up = "../../../"
        path = f"guide/metro/{s['id']}/"
        label, name = station_label(s), short_name(s)
        line = LINES.get(s["line"], s["line"])
        first = near[0]
        lead = (f"{len(near)} Durga Puja pandals are within a {NEAR_MIN}-minute walk of {esc(label)} on the {esc(line)}. "
                f"The closest is {esc(first[2]['name'])}, about {first[0]} minutes on foot ({km(first[1])}). "
                f"In {self.year} the puja runs from Panchami, {nice_date(self.start, True)}, to Dashami, {nice_date(self.end, True)}. "
                f"Walking times assume festival crowds; the quiet hours are estimates from our crowd model, not live counts.")
        rows = "".join(
            f"<li>{self.link_pandal(p['id'], up)}: <b>{w} min walk</b> ({km(m)}){self.theme_note(p)}"
            f"<br><small>{esc(p['highlight'])} Best time: {esc(p['best_slot_label'])}; quietest on Ashtami: {hrange(p['quiet_hours']['ashtami'])}.</small></li>"
            for w, m, p in near)
        wa = (f"Durga Puja {self.year}: pandals near {label}\n"
              + "\n".join(f"• {p['name']} ({w} min walk)" for w, _, p in near[:6])
              + f"\n\nQuiet hours and directions: {self.url(path)}?src=wa_metro")
        same_line = [x for x, _ in self.metro if x["line"] == s["line"] and x["id"] != s["id"]]
        others = " · ".join(self.link_station(x["id"], up) for x in same_line)
        top = max(near, key=lambda x: (x[2]["popularity"], -x[0]))[2]
        qa = [(f"Which Durga Puja pandals are near {name} metro?" if s["line"] != "suburban" else f"Which Durga Puja pandals are near {name} station?",
               "; ".join(f"{esc(p['name'])} ({w} min walk)" for w, _, p in near[:8]) + "."),
              (f"How far is {first[2]['name']} from {name}?", f"About {km(first[1])}, roughly {first[0]} minutes on foot through the puja crowds."),
              (f"When is {top['name']} least crowded?", f"On Saptami the quietest window is {hrange(top['quiet_hours']['saptami'])}, and on Ashtami {hrange(top['quiet_hours']['ashtami'])}. Evenings from 6 pm to midnight are the busiest."),
              (f"Does the metro run late during Durga Puja {self.year}?", self.nights_answer(up))]
        faq_html, faq_ld = self.faq(qa)
        body = f"""<article>
<h1>Durga Puja pandals near {esc(label)} ({self.year})</h1>
<p class="lead">{lead}</p>
<ol class="list">{rows}</ol>
{share_bar(wa)}
<p><a class="cta" href="{up}?src=seo_metro#plan">Plan a walking route from here in the app →</a></p>
{self.notices_html(up)}
{f'<h2>More stations on the {esc(line)}</h2><p>{others}</p>' if others else ''}
<p><a href="{up}guide/metro/">All stations and their pandals</a> · <a href="{up}guide/best-pandals-{self.year}/">Best pandals {self.year}</a> · <a href="{up}guide/dates/">Durga Puja {self.year} dates</a></p>
{faq_html}
</article>"""
        items = {"@context": "https://schema.org", "@type": "ItemList", "name": f"Durga Puja pandals near {label}", "numberOfItems": len(near),
                 "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": self.url(f"guide/pandals/{p['id']}/"), "name": p["name"]} for i, (_, _, p) in enumerate(near)]}
        title_name = name if s["line"] != "suburban" else f"{name} Station"
        self.page(path, f"Durga Puja Pandals Near {title_name}{' Metro' if s['line'] != 'suburban' else ''} {self.year}",
                  f"{len(near)} Durga Puja pandals within a {NEAR_MIN}-minute walk of {label}: walking times, {self.year} themes and the quietest hours. "
                  f"Closest: {first[2]['name']}.",
                  body, ld=(items, faq_ld), crumbs=(("Durga Puja guide", "guide/"), ("By metro", "guide/metro/"), (name, path)),
                  priority=0.8, summary=re.sub(r"<[^>]+>", "", lead), app_link="#plan")
        self.full.append(f"## Pandals near {label}\n{re.sub(r'<[^>]+>', '', lead)}\n"
                         + "\n".join(f"- {p['name']}: {w} min walk" for w, _, p in near) + f"\nPage: {self.url(path)}\n")

    def metro_hub(self):
        up = "../../"
        path = "guide/metro/"
        by = {}
        far = []
        for p in self.g["pandals"]:
            (far if self.metro_far(p) else by.setdefault(p["nearest_metro"]["id"], [])).append(p)
        on_line = {}
        for sid, ps in by.items():
            on_line.setdefault(self.station[sid]["line"], 0)
            on_line[self.station[sid]["line"]] += len(ps)
        best_line = max(on_line, key=on_line.get)
        n_near = sum(on_line.values())
        lead = (f"The metro is the quickest way to go pandal hopping in Kolkata: most neighbourhood lanes close to cars on puja evenings. "
                f"{n_near} of the {len(self.g['pandals'])} pandals in this guide are within a {FAR_MIN}-minute walk of a metro or suburban station, "
                f"{on_line[best_line]} of them closest to the {esc(LINES[best_line])}. Below, every pandal is listed under its nearest station, "
                f"with the walk in festival crowds. The puja runs from Panchami, {nice_date(self.start, True)}, to Dashami, {nice_date(self.end, True)}.")
        sections = []
        for ln in LINE_ORDER:
            sts = [s for s in self.g["transit"] if s["line"] == ln and s["id"] in by]
            if not sts:
                continue
            lis = "".join(
                f"<li><b>{self.link_station(s['id'], up)}</b>: "
                + ", ".join(f"{self.link_pandal(p['id'], up)} <small>{p['nearest_metro']['walk_min']} min</small>"
                            for p in sorted(by[s["id"]], key=lambda p: p["nearest_metro"]["walk_min"])) + "</li>"
                for s in sts)
            sections.append(f"<h2>{esc(LINES[ln][0].upper() + LINES[ln][1:])}</h2><ul>{lis}</ul>")
        far_html = ""
        if far:
            far_html = ("<h2>No metro within walking distance</h2><p>Take an auto, bus or cab for the last stretch to these. "
                        "The pandal pages list the buses and autos.</p><ul>"
                        + "".join(f"<li>{self.link_pandal(p['id'], up)} <small>({esc(self.zone[p['zone']]['name'])}; nearest station {esc(short_name(self.station[p['nearest_metro']['id']]))}, {km(p['nearest_metro']['distance_m'])} away)</small></li>"
                                  for p in sorted(far, key=lambda p: (p["zone"], p["name"]))) + "</ul>")
        stations_html = " · ".join(f"<a href='{up}guide/metro/{s['id']}/'>{esc(short_name(s))}</a>" for s, _ in self.metro)
        top = sorted((p for p in self.g["pandals"] if not self.metro_far(p)), key=lambda p: (-p["popularity"], p["name"]))[:4]
        qa = [(f"Does Kolkata Metro run all night during Durga Puja {self.year}?", self.nights_answer(up)),
              ("Which metro line is best for pandal hopping?", f"The {esc(LINES[best_line])}: {on_line[best_line]} of the pandals in this guide are closest to one of its stations, "
               "from Shyambazar, Sovabazar and Girish Park in the north to Jatin Das Park and Kalighat in the south."),
              *[(f"Which metro station is nearest to {p['name']}?", f"{esc(short_name(self.station[p['nearest_metro']['id']]))} ({esc(LINES.get(p['nearest_metro']['line'], ''))}), "
                 f"about {km(p['nearest_metro']['distance_m'])} away, roughly {p['nearest_metro']['walk_min']} minutes on foot.") for p in top]]
        faq_html, faq_ld = self.faq(qa)
        wa = (f"Durga Puja {self.year} by metro: which pandals are walkable from each Kolkata metro station, nearest first, "
              f"with the quiet hours.\n{self.url(path)}?src=wa_metro")
        body = f"""<article>
<h1>Kolkata Durga Puja {self.year} by metro: pandals near every station</h1>
<p class="lead">{lead}</p>
{share_bar(wa)}
{self.notices_html(up)}
<p><b>Station guides:</b> {stations_html}</p>
{''.join(sections)}
{far_html}
<p><a href="{up}guide/best-pandals-{self.year}/">Best pandals {self.year}</a> · <a href="{up}guide/parking/">Park and ride</a> · <a href="{up}guide/">All areas</a></p>
{faq_html}
</article>"""
        items = {"@context": "https://schema.org", "@type": "ItemList", "name": f"Kolkata metro stations near Durga Puja pandals, {self.year}", "numberOfItems": len(self.metro),
                 "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": self.url(f"guide/metro/{s['id']}/"), "name": station_label(s)} for i, (s, _) in enumerate(self.metro)]}
        self.page(path, f"Durga Puja {self.year} by Metro: Pandals Near Every Kolkata Station",
                  f"Kolkata Durga Puja {self.year} by metro: every pandal under its nearest metro station with walking times, plus Metro's puja timings as they're announced.",
                  body, ld=(items, faq_ld), crumbs=(("Durga Puja guide", "guide/"), ("By metro", path)), priority=0.95,
                  summary=re.sub(r"<[^>]+>", "", lead), app_link="#plan")
        self.full.append(f"## Durga Puja by metro\n{re.sub(r'<[^>]+>', '', lead)}\n{re.sub(r'<[^>]+>', '', self.nights_answer())}\nPage: {self.url(path)}\n")

    # ------------------------------------------------------------------ late night
    def late_night_page(self):
        """/guide/late-night-pandal-hopping/: how the night thins out (crowd model), the all-nighter route, food open
        past midnight and getting home by metro, for 'late night pandal hopping kolkata' and 'is metro open all night'."""
        up = "../../"
        path = "guide/late-night-pandal-hopping/"
        hf = self.meta["model"]["hour_factors"]
        pct = lambda h: round(hf[h] / max(hf) * 100)   # noqa: E731  share of the evening peak
        hours = [22, 0, 1, 2, 3, 4, 5]
        lead = (f"On the big nights of Durga Puja {self.year}, Saptami to Navami ({nice_date(self.days['saptami']['date'])} to "
                f"{nice_date(self.days['navami']['date'])}), many Kolkata pandals stay open late and the streets stay full past midnight. "
                f"Our crowd model puts the crowd at midnight at about {pct(0)}% of the 8 pm peak, {pct(2)}% by 2 am and {pct(4)}% by 4 am; "
                f"4 to 7 am is the quietest window of the whole day. These are estimates, not live counts. Below: the hours, the "
                f"all-night route, food that's open late and how to get home.")
        tbl = ("<table class='days'><thead><tr><th>Time</th><th>Crowd (share of the 8 pm peak)</th></tr></thead><tbody>"
               + "".join(f"<tr><td>{'midnight' if h == 0 else (str(h - 12) + ' pm' if h > 12 else str(h) + ' am')}</td><td>about {pct(h)}%</td></tr>" for h in hours)
               + "</tbody></table>")
        trail = next((t for t in self.g["itineraries"] if t["id"] == "all_nighter"), None)
        trail_html = ""
        if trail:
            stops = [s for seg in trail["segments"] for s in seg.get("stops", []) if s.get("pandal") in self.pandal]
            trail_html = (f"<h2>The all-night route</h2><p><a href='{up}guide/trails/{trail['id']}/'>{esc(trail['name'])}</a>: {esc(trail['blurb'])} "
                          f"It assumes the metro runs through the night; until Metro confirms that, plan a cab or auto between clusters.</p><ol class='list'>"
                          + "".join(f"<li><b>{esc(s.get('arrive', ''))}</b> {self.link_pandal(s['pandal'], up)}</li>" for s in stops) + "</ol>")
        top = sorted(self.g["pandals"], key=lambda p: (-p["popularity"], -p["crowd_base"], p["name"]))[:12]
        groups = {}
        for p in top:   # pandals with the same night pattern share one line
            key = tuple(crowd_word(self.hour_crowd(p, "ashtami", h)) for h in (20, 2, 5))
            groups.setdefault(key, []).append(p)
        big = ("<h2>Big pandals to save for after 2 am</h2><p>The famous queues shrink most in the small hours. On Ashtami, by our model's estimate:</p><ul>"
               + "".join(f"<li>{', '.join(self.link_pandal(p['id'], up) for p in ps)}: {k[0]} at 8 pm, {k[1]} at 2 am, {k[2]} by 5 am.</li>" for k, ps in groups.items())
               + "</ul>")

        def closes_late(hrs):   # '16:00-01:00' closes after midnight; '12:00-00:00' closes at midnight
            m = re.fullmatch(r"\d\d:\d\d-(\d\d):(\d\d)", hrs or "")
            return bool(m) and 0 <= int(m.group(1)) < 6 and (m.group(1), m.group(2)) != ("00", "00")

        late = sorted((f for f in self.g["food"] if closes_late(f.get("hours"))), key=lambda f: (f["zone"], f["name"]))
        food_html = ("<h2>Food open past midnight</h2><p>Usual hours; many places stay open later on puja nights, but check before you go.</p><ul>"
                     + "".join(f"<li>{self.link_food(f['id'], up)} <small>({esc(self.zone[f['zone']]['name'] if f['zone'] in self.zone else f['zone'])})</small>: "
                               f"open {esc(f['hours'].replace('-', ' to '))}"
                               + (f" · near {esc(short_name(self.station[f['nearest_metro']['id']]))} {'station' if f['nearest_metro']['line'] == 'suburban' else 'metro'}" if f.get("nearest_metro") and f["nearest_metro"]["walk_min"] <= FAR_MIN and f["nearest_metro"]["id"] in self.station else "")
                               + "</li>" for f in late) + "</ul>") if late else ""
        safety = ("<h2>Staying together at night</h2><ul><li>Fix a meeting point at each pandal before you go in; phones can lose signal in the crowd.</li>"
                  "<li>Carry water, a charged phone and some cash; UPI can fail when the network is jammed.</li>"
                  "<li>Kolkata Police run help booths at the big pandals, and their Puja Bandhu app shows live crowd counts.</li>"
                  "<li>Wear shoes you can walk 10 km in. The all-night route is about that.</li></ul>")
        qa = [("Are Kolkata pandals open all night during Durga Puja?", f"Many of the big pandals stay open late into the night from Saptami to Navami, and the streets stay busy past midnight. Timings are set by each committee, so check the pandal's own notice."),
              ("What is the least crowded time to visit pandals at night?", f"After 2 am the crowd falls fast: our model estimates about {pct(2)}% of the evening peak at 2 am and {pct(4)}% at 4 am. 4 to 7 am is the quietest window of the day."),
              (f"Does Kolkata Metro run all night during Durga Puja {self.year}?", self.nights_answer(up))]
        faq_html, faq_ld = self.faq(qa)
        wa = (f"Late-night pandal hopping, Durga Puja {self.year}: when the crowds thin after midnight, the all-night route "
              f"and food open late.\n{self.url(path)}?src=wa_night")
        body = f"""<article>
<h1>Late-night pandal hopping in Kolkata: Durga Puja {self.year}</h1>
<p class="lead">{lead}</p>
{share_bar(wa)}
<h2>How the night thins out</h2>
{tbl}
{self.notices_html(up)}
{trail_html}
{big}
{food_html}
{safety}
<p><a href="{up}guide/metro/">Pandals by metro station</a> · <a href="{up}guide/best-pandals-{self.year}/">Best pandals {self.year}</a> · <a href="{up}guide/dates/">Durga Puja {self.year} dates</a></p>
{faq_html}
</article>"""
        self.page(path, f"Late-Night Pandal Hopping in Kolkata: Durga Puja {self.year}",
                  f"Late-night pandal hopping, Durga Puja {self.year}: when the crowds thin after midnight, the all-night route, food open late and the metro at night.",
                  body, ld=(faq_ld,), crumbs=(("Durga Puja guide", "guide/"), ("Late night", path)), priority=0.9,
                  summary=re.sub(r"<[^>]+>", "", lead), app_link="#trail=all_nighter")
        self.full.append(f"## Late-night pandal hopping\n{re.sub(r'<[^>]+>', '', lead)}\nPage: {self.url(path)}\n")

    # ------------------------------------------------------------------ web stories from the data
    def pandal_photo(self, p):
        """The pandal's most recent freely licensed Commons photo, for a data story page (None if it has none)."""
        ph = sorted((x for x in p.get("photos", []) if x.get("src", "").startswith("https://") and x.get("author") and x.get("license")),
                    key=lambda x: -(x.get("year") or 0))
        if not ph:
            return None
        x = ph[0]
        return {"src": x["src"], "author": x["author"], "license": x["license"], "year": x.get("year"), "alt": f"{p['name']} Durga Puja"}

    def data_stories(self):
        """Two timely Web Stories built from the guide's data: the 2026 themes and the pandals by metro station. They
        use each pandal's own Commons photo, credited with its year, so a photo is never passed off as this year's."""
        out, gen = [], ["pandal-lights", "pandal-art", "crowd", "dhaki", "dhunuchi", "kolkata"]
        themed = sorted((p for p in self.g["pandals"] if p.get("theme_2026") and p["theme_2026"].get("title")),
                        key=lambda p: (-p["popularity"], p["name"]))
        pages = []
        for p in themed:
            pic = self.pandal_photo(p)
            if not pic:
                continue
            th = p["theme_2026"]
            about = re.split(r"(?<=[.!?])\s", th.get("about", ""), maxsplit=1)[0]
            pages.append({"image": pic, "kicker": self.zone[p["zone"]]["name"], "heading": p["name"],
                          "text": f"{self.year} theme: {th['title']}." + (f" {about}" if about and about != th["title"] else ""),
                          "link": f"guide/pandals/{p['id']}/"})
            if len(pages) == 8:
                break
        if len(pages) >= 4:
            out.append({"slug": f"durga-puja-{self.year}-themes", "title": f"Durga Puja {self.year} themes: Kolkata's big pandals",
                        "dek": f"What Kolkata's best-known pandals are building for {self.year}, as reported so far. Each photo is captioned with the year it was taken.",
                        "article": f"guide/themes-{self.year}/", "cover": "pandal-art", "pages": pages, "music": "story_dhak"})
        ranked = sorted(self.metro, key=lambda x: (-sum(p["popularity"] for _, _, p in x[1]), x[0]["name"]))
        pages = []
        for n, (st, near) in enumerate(ranked[:8]):
            star = max(near, key=lambda x: (x[2]["popularity"], -x[0]))[2]
            pages.append({"image": self.pandal_photo(star) or gen[n % len(gen)], "kicker": LINES.get(st["line"], st["line"]),
                          "heading": station_label(st)[0].upper() + station_label(st)[1:],
                          "text": "Within a short walk: " + ", ".join(f"{p['name']} ({w} min)" for w, _, p in near[:4]) + ".",
                          "link": f"guide/metro/{st['id']}/"})
        if len(pages) >= 4:
            out.append({"slug": f"durga-puja-{self.year}-by-metro", "title": f"Durga Puja {self.year} by metro: pandals near each station",
                        "dek": "Which pandals are a short walk from each Kolkata metro station, nearest first.",
                        "article": "guide/metro/", "cover": "crowd", "pages": pages, "music": "story_dhak"})
        return out
