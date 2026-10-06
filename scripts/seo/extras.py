"""Site pages and tools beyond the articles: About, Contact, Terms, Search, the Durga Puja 2026 calendar (.ics),
the Bijoya card maker, and the AdSense switch (site.json "adsense_client") with its ads.txt."""
import html
import json
import re
from datetime import date, timedelta

from .common import NAME, esc, nice_date

CONTACT = "workdesk94@gmail.com"

# Short greetings for the card maker (our own words)
CARD_LINES = [
    ("শুভ বিজয়া", "Subho Bijoya! May Ma Durga's blessings stay with you all year."),
    ("শুভ বিজয়া", "Wishing you love, light and a sweet Bijoya with family."),
    ("আসছে বছর আবার হবে", "Asche bochor abar hobe: see you next year, Ma."),
    ("শুভ শারদীয়া", "Subho Sharodiya! Wishing you a joyful, safe pujo."),
    ("শুভ শারদীয়া", "May this pujo bring new beginnings and old friends together."),
    ("শুভ মহালয়া", "Subho Mahalaya: the countdown to Ma's homecoming begins."),
    ("শুভ মহাষ্টমী", "Subho Maha Ashtami: may your anjali bring you peace."),
    ("শুভ দীপাবলি", "Subho Dipaboli: light, sweets and good company."),
]


def ics_fold(line):
    """RFC 5545: lines longer than 75 octets continue on the next line after a space."""
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def ics_escape(s):
    return s.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


class ExtrasMixin:
    """Mixed into build_seo.Site."""

    # ------------------------------------------------------------------ AdSense
    def ads_head(self):
        """The AdSense tag, only when site.json has an "adsense_client" (ca-pub-…); Auto ads are configured in AdSense."""
        if not self.adsense:
            return ""
        c = esc(self.adsense)
        return (f'\n<meta name="google-adsense-account" content="{c}">'
                f'\n<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={c}" crossorigin="anonymous"></script>')

    def write_ads_txt(self):
        if self.adsense.startswith("ca-pub-"):
            (self.out / "ads.txt").write_text(f"google.com, {self.adsense.replace('ca-', '', 1)}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")

    # ------------------------------------------------------------------ About, Contact, Terms
    def site_pages(self):
        n_articles, n_pandals = len(self.articles), len(self.g["pandals"])
        about = f"""<article>
<h1>About {NAME}</h1>
<p class="lead">{NAME} is a free, independent guide to Durga Puja: what it means, how each day's rituals are performed, how to celebrate at home,
and a live Kolkata guide to {n_pandals} pandals. It has {n_articles} in-depth articles today and grows every season.</p>
<h2 id="what">What you'll find here</h2>
<ul>
<li><a href="../durga-puja/">The Durga Puja guide</a>: meaning, history, the goddess, rituals day by day, mantras, recipes, Navratri and the festivals around it.</li>
<li><a href="../guide/">The Kolkata {self.year} guide</a>: every listed pandal with the best time to visit, metro, food and parking.</li>
<li><a href="../">The app</a>: live check-ins and crowd levels, route planning, a step counter, Pujo Radio and moments shared by visitors.</li>
</ul>
<h2 id="how">How we write and check</h2>
<p>Articles are researched from published sources, which each article lists at the end, and drafted with the help of AI writing tools.
They are then checked against those sources before publishing. Durga Puja is a living tradition, and practice differs between families,
regions and panjikas (almanacs), so we say where traditions differ instead of presenting one way as the only one. We don't give
exact muhurta timings; please confirm those with your purohit or local panjika.</p>
<p>Kolkata facts (pandal locations, metro, food, parking) come from a curated dataset, checked against OpenStreetMap. Crowd levels and best
times are estimates from our crowd model, not live counts, except where the app shows live check-ins.</p>
<h2 id="independent">Independent</h2>
<p>{NAME} is not affiliated with any puja committee, temple, government body or brand. Restaurant offers shown in the app are verified by a call
to the owner before they appear. Pages may show advertising, which pays for running the guide. Ads are never mixed into the text of an article.</p>
<h2 id="corrections">Corrections</h2>
<p>Spotted a mistake, or does your family do it differently? Write to <a href="mailto:{CONTACT}">{CONTACT}</a> and we'll look at it quickly.
Every article shows when it was last updated.</p>
</article>"""
        self.page("about/", f"About {NAME}: an independent Durga Puja guide", f"Who makes {NAME}, how articles are researched and checked, how we handle corrections, and how the free guide is funded.",
                  about, crumbs=(("About", "about/"),), priority=0.4, app_link=None, ads=False,
                  ld=({"@context": "https://schema.org", "@type": "AboutPage", "name": f"About {NAME}", "url": self.url("about/"),
                       "about": {"@type": "Organization", "name": NAME, "url": self.base, "email": CONTACT}},),
                  note="")
        contact = f"""<article>
<h1>Contact {NAME}</h1>
<p class="lead">Email us at <a href="mailto:{CONTACT}">{CONTACT}</a>. We read everything and usually reply within a few days.</p>
<h2 id="topics">Write to us about</h2>
<ul>
<li><b>Corrections and additions</b> to any article or pandal page: please include the page link.</li>
<li><b>Restaurants</b>: post a pujo offer from your eatery's page in the app, or email us.</li>
<li><b>Puja committees</b>: send your pandal's theme, timings and location to be listed or updated.</li>
<li><b>Your data</b>: to have anything removed, use “Delete all my data” in the app (My Pujo → Settings) or email us. See the <a href="../privacy.html">privacy policy</a>.</li>
<li><b>Press and partnerships.</b></li>
</ul>
</article>"""
        self.page("contact/", f"Contact {NAME}: corrections, listings and data requests", f"How to reach {NAME}: email for corrections, pandal listings, restaurant offers, data requests, press and partnerships.",
                  contact, crumbs=(("Contact", "contact/"),), priority=0.3, app_link=None, ads=False,
                  ld=({"@context": "https://schema.org", "@type": "ContactPage", "name": f"Contact {NAME}", "url": self.url("contact/")},), note="")
        terms = f"""<article>
<h1>Terms of use</h1>
<p class="lead">By using {NAME} (this website and the app) you agree to these terms. They are short: use the guide in good faith,
check important details locally, and respect other people's content.</p>
<h2 id="information">Information, not advice</h2>
<p>We work hard to keep the guide accurate, but ritual practice varies and festival details (timings, routes, traffic rules, opening hours,
prices) change every year. The guide is provided “as is”, without warranties. Confirm anything important (muhurta, travel, medical or
dietary matters) with the right local source. {NAME} isn't liable for losses arising from use of the guide.</p>
<h2 id="content">Our content</h2>
<p>Articles, pages and the app's design are © {NAME}. You're welcome to quote short passages with a link to the page. Photos from
Wikimedia Commons belong to their authors and are used under the licences shown with each photo.</p>
<h2 id="yours">What you post</h2>
<p>Photos, videos, ratings and offers you post must be your own or yours to share, lawful, and respectful. Don't post other people in
ways they wouldn't agree to. We may remove anything that breaks these rules, and three reports from visitors hide a post automatically.
You keep ownership of what you post; by posting, you let us show it in the guide.</p>
<h2 id="ads">Advertising and links</h2>
<p>Some pages may show ads, served by Google AdSense, and the guide links to other websites. We don't control those sites or ads and
aren't responsible for them.</p>
<h2 id="privacy">Privacy</h2>
<p>How we handle data is explained in the <a href="../privacy.html">privacy policy</a>.</p>
<h2 id="changes">Changes and contact</h2>
<p>We may update these terms; the date below shows the latest version. Questions: <a href="mailto:{CONTACT}">{CONTACT}</a>.</p>
</article>"""
        self.page("terms/", f"Terms of use | {NAME}", f"The terms for using {NAME}: information not advice, our content and yours, advertising, links and how to contact us.",
                  terms, crumbs=(("Terms", "terms/"),), priority=0.2, app_link=None, ads=False, note=f"Last updated {nice_date(self.updated, True)}.")

    # ------------------------------------------------------------------ Search
    def search_page(self):
        """A small client-side search over every page (articles first), from guide/search-index.json."""
        types = {a.path: a.type for a in self.articles}
        kw = {a.path: " ".join(a.meta.get("keywords", [])) for a in self.articles}
        clean = lambda x: html.unescape(re.sub(r"<[^>]+>", "", x or ""))  # noqa: E731
        docs = [{"u": self.url(p), "t": clean(t.split(" | ")[0]), "s": clean(s)[:220], "k": kw.get(p, ""), "y": types.get(p, "Place")}
                for p, t, s, _ in self.pages if p not in ("about/", "contact/", "terms/")]
        (self.out / "guide" / "search-index.json").write_text(json.dumps(docs, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        body = f"""<article>
<h1>Search the Durga Puja guide</h1>
<form class="search" role="search" onsubmit="return false"><label for="q" class="sr">Search</label>
<input id="q" type="search" placeholder="Try: anjali mantra, Sandhi Puja, khichuri, Sreebhumi" autocomplete="off" disabled></form>
<ol id="results" class="results" data-index="../guide/search-index.json" aria-live="polite"></ol>
<p class="fine">Searches {len(docs)} pages: every article on rituals, mantras, recipes, Navratri and festivals, and every Kolkata pandal and eatery.</p>
</article>"""
        self.page("search/", f"Search | {NAME}", f"Search {len(docs)} pages on Durga Puja: rituals, mantras, recipes, Navratri, festivals and every Kolkata pandal and eatery.",
                  body, crumbs=(("Search", "search/"),), app_link=None, ads=False, index=False, note="")

    # ------------------------------------------------------------------ Calendar
    def calendar(self):
        """durga-puja-2026.ics: every puja day as an all-day event, each linked to its rituals article."""
        now = "20261006T000000Z"
        ev = []
        for d in self.meta["days"]:
            day = date.fromisoformat(d["date"])
            path = f"durga-puja/rituals/{d['id']}/"
            link = self.url(path) if path in self.by_path else self.url("guide/dates/")
            ev.append("\r\n".join(ics_fold(x) for x in [
                "BEGIN:VEVENT", f"UID:{d['id']}-{self.year}@{self.base.split('//')[1].strip('/')}", f"DTSTAMP:{now}",
                f"DTSTART;VALUE=DATE:{day:%Y%m%d}", f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
                f"SUMMARY:{ics_escape(d['name'] + ' (' + d['name_bn'] + ') · Durga Puja ' + str(self.year))}",
                f"DESCRIPTION:{ics_escape('What happens today and how to plan your pandal hopping: ' + link)}", f"URL:{link}", "TRANSP:TRANSPARENT", "END:VEVENT"]))
        cal = "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:-//{NAME}//Durga Puja {self.year}//EN", "CALSCALE:GREGORIAN",
                           f"X-WR-CALNAME:Durga Puja {self.year}", *ev, "END:VCALENDAR"]) + "\r\n"
        (self.out / f"durga-puja-{self.year}.ics").write_text(cal, encoding="utf-8")

    def calendar_html(self, up):
        gcal = "".join(f"<li><a rel='noopener' href='https://calendar.google.com/calendar/render?action=TEMPLATE&amp;text={esc(d['name'])}+%C2%B7+Durga+Puja+{self.year}"
                       f"&amp;dates={d['date'].replace('-', '')}/{(date.fromisoformat(d['date']) + timedelta(days=1)):%Y%m%d}"
                       f"&amp;details={esc(self.url('guide/dates/'))}'>{esc(d['name'])}, {nice_date(d['date'])}</a></li>" for d in self.meta["days"])
        return (f"<div class='calendar'><a class='cta small' href='{up}durga-puja-{self.year}.ics' download>📅 Add all puja days to your calendar (.ics)</a>"
                f"<details><summary>Or add one day to Google Calendar</summary><ul>{gcal}</ul></details></div>")

    # ------------------------------------------------------------------ Bijoya card maker
    def card_tool(self):
        options = "".join(f'<option value="{i}">{esc(bn)}: {esc(en)}</option>' for i, (bn, en) in enumerate(CARD_LINES))
        lines = json.dumps(CARD_LINES, ensure_ascii=False)
        body = f"""<article>
<h1>Bijoya and Sharodiya greeting card maker</h1>
<p class="lead">Make a greeting card for Bijoya Dashami, Mahalaya or the pujo in a few seconds: pick a wish, add your name, and download or share
it on WhatsApp and Instagram. Free, nothing to install, and nothing you type leaves your phone.</p>
<form class="card-form" onsubmit="return false">
<label>Greeting<select id="cLine">{options}</select></label>
<label>From<input id="cName" maxlength="40" placeholder="Your name (optional)"></label>
<label>Style<select id="cStyle"><option value="0">Alta red</option><option value="1">Shiuli white</option><option value="2">Night gold</option></select></label>
</form>
<canvas id="card" width="1080" height="1350" aria-label="Your greeting card"></canvas>
<div class="share"><button class="sb wa" type="button" id="cShare">Share</button><button class="sb" type="button" id="cSave">Download</button></div>
<p class="fine">Looking for more words? See <a href="../../durga-puja/bijoya-dashami-wishes/">Bijoya Dashami wishes</a> in Bengali, English and Hindi.</p>
</article>
<script>
(function () {{
  var LINES = {lines}, STYLES = [["#9F1239", "#7A0E2B", "#FDE68A", "#FFFFFF"], ["#FFFBF2", "#F6E7CF", "#9F1239", "#3B2A20"], ["#1A1210", "#2B1A12", "#FBBF24", "#F5EEE8"]];
  var cv = document.getElementById('card'), x = cv.getContext('2d');
  function wrap(t, maxW) {{ var w = t.split(' '), out = [], l = ''; w.forEach(function (s) {{ var n = l ? l + ' ' + s : s; if (x.measureText(n).width > maxW && l) {{ out.push(l); l = s; }} else l = n; }}); out.push(l); return out; }}
  function draw() {{
    var L = LINES[+document.getElementById('cLine').value], S = STYLES[+document.getElementById('cStyle').value], name = document.getElementById('cName').value.trim();
    var g = x.createLinearGradient(0, 0, 0, 1350); g.addColorStop(0, S[0]); g.addColorStop(1, S[1]); x.fillStyle = g; x.fillRect(0, 0, 1080, 1350);
    x.strokeStyle = S[2]; x.lineWidth = 6; x.strokeRect(50, 50, 980, 1250); x.lineWidth = 2; x.strokeRect(70, 70, 940, 1210);
    x.fillStyle = S[2]; x.textAlign = 'center'; x.font = '160px serif'; x.fillText('🪔', 540, 330);
    x.font = 'bold 110px "Noto Sans Bengali", "Hind Siliguri", sans-serif'; x.fillText(L[0], 540, 560);
    x.fillStyle = S[3]; x.font = '54px system-ui, sans-serif';
    wrap(L[1], 860).forEach(function (l, i) {{ x.fillText(l, 540, 720 + i * 74); }});
    if (name) {{ x.fillStyle = S[2]; x.font = 'italic 58px Georgia, serif'; x.fillText('— ' + name, 540, 1080); }}
    x.fillStyle = S[3]; x.globalAlpha = 0.75; x.font = '34px system-ui, sans-serif'; x.fillText('{esc(self.base.split("//")[1].strip("/"))}', 540, 1240); x.globalAlpha = 1;
  }}
  function blob(cb) {{ cv.toBlob(cb, 'image/png'); }}
  ['cLine', 'cName', 'cStyle'].forEach(function (id) {{ document.getElementById(id).addEventListener('input', draw); }});
  document.getElementById('cSave').onclick = function () {{ blob(function (b) {{ var a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = 'bijoya-card.png'; a.click(); }}); }};
  document.getElementById('cShare').onclick = function () {{
    blob(function (b) {{
      var f = new File([b], 'bijoya-card.png', {{ type: 'image/png' }});
      if (navigator.canShare && navigator.canShare({{ files: [f] }})) navigator.share({{ files: [f], text: LINES[+document.getElementById('cLine').value][1] }}).catch(function () {{}});
      else document.getElementById('cSave').click();
    }});
  }};
  draw(); if (document.fonts) document.fonts.ready.then(draw);
}})();
</script>"""
        self.page("tools/bijoya-card/", f"Bijoya Dashami greeting card maker (free) | {NAME}",
                  "Make a free Bijoya Dashami, Mahalaya or Sharodiya greeting card with your name in seconds. Download it or share it on WhatsApp and Instagram.",
                  body, crumbs=(("Bijoya card maker", "tools/bijoya-card/"),), priority=0.7, app_link=None,
                  ld=({"@context": "https://schema.org", "@type": "WebApplication", "name": "Bijoya greeting card maker", "url": self.url("tools/bijoya-card/"),
                       "applicationCategory": "DesignApplication", "operatingSystem": "Any (web browser)", "isAccessibleForFree": True,
                       "offers": {"@type": "Offer", "price": "0", "priceCurrency": "INR"}},),
                  note="Cards are drawn on your phone; nothing you type is sent anywhere.")

    def build_extras(self):
        self.site_pages()
        self.card_tool()
        self.calendar()
        self.search_page()   # last: it indexes everything above
        self.write_ads_txt()
