"""The crawlable guide pages (scripts/build_seo.py): every page is complete, linked and machine-readable."""
import json
import re
import shutil
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_seo  # noqa: E402
from seo.knowledge import CONTENT, Article  # noqa: E402
from seo.markdown import render  # noqa: E402


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = self.desc = self.canonical = None
        self.h1 = 0
        self.links, self.ld, self._ld, self._title = [], [], None, False

    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag == "title":
            self._title = True
        elif tag == "meta" and a.get("name") == "description":
            self.desc = a.get("content")
        elif tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href")
        elif tag == "h1":
            self.h1 += 1
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._ld = ""

    def handle_endtag(self, tag):
        if tag == "title":
            self._title = False
        if tag == "script" and self._ld is not None:
            self.ld.append(json.loads(self._ld))
            self._ld = None

    def handle_data(self, d):
        if self._title:
            self.title = (self.title or "") + d
        if self._ld is not None:
            self._ld += d


SITE_PAGES = ("about/", "contact/", "terms/", "tools/bijoya-card/", "guides/")   # indexed; search/ is noindex


class BuildSeoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        shutil.copy(ROOT / "app" / "index.html", cls.tmp / "index.html")
        cls.g = json.loads((ROOT / "app" / "data" / "guide.json").read_text(encoding="utf-8"))
        cls.base = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))["url"]
        cls.n = build_seo.Site(cls.g, cls.base, cls.tmp).build()
        cls.articles = [Article(f) for f in sorted(CONTENT.rglob("*.md")) if f.name != "README.md"]
        cls.pages = sorted([cls.tmp / "guide" / "index.html", *cls.tmp.glob("guide/**/index.html")]
                           + [cls.tmp / a.path / "index.html" for a in cls.articles])
        cls.pages = sorted(set(cls.pages))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_one_page_per_place_area_and_trail(self):
        g = self.g
        want = len(g["pandals"]) + len(g["food"]) + len(g["zones"]) + len(g["itineraries"]) + 3 + len(self.articles)  # + hub, dates, parking
        import tomllib
        stories = len(tomllib.loads((CONTENT / "stories.toml").read_text(encoding="utf-8"))["story"]) if (self.tmp / "stories").exists() else 0
        self.assertEqual(self.n, want + len(SITE_PAGES) + stories + (1 if stories else 0))   # + the stories index
        self.assertEqual(len(self.pages), want)

    def test_every_page_is_complete(self):
        for f in self.pages:
            p = Page()
            p.feed(f.read_text(encoding="utf-8"))
            rel = f.parent.relative_to(self.tmp).as_posix() + "/"
            with self.subTest(page=rel):
                self.assertTrue(p.title and 20 <= len(p.title) <= 120, p.title)
                self.assertTrue(p.desc and 50 <= len(p.desc) <= 320, p.desc)
                self.assertEqual(p.canonical, self.base + rel)
                self.assertEqual(p.h1, 1)
                types = {x["@type"] for x in p.ld}
                self.assertIn("BreadcrumbList", types)
                if "/pandals/" in rel:
                    self.assertTrue({"TouristAttraction", "Event", "FAQPage"} <= types, types)
                if "/food/" in rel:
                    self.assertTrue(types & {"Restaurant", "FoodEstablishment"}, types)
                if not rel.startswith("guide/"):   # knowledge articles
                    self.assertTrue(types & {"Article", "HowTo", "Recipe"}, types)

    def test_internal_links_resolve(self):
        for f in self.pages:
            p = Page()
            p.feed(f.read_text(encoding="utf-8"))
            for href in p.links:
                if re.match(r"^(https?:|mailto:|#)", href):
                    continue
                target = (f.parent / href.split("#")[0]).resolve()
                if href.split("#")[0] in ("", "./") or str(target) == str(self.tmp.resolve()):
                    continue   # the app itself
                if target.suffix in (".txt", ".html", ".json", ".xml", ".ics"):
                    if target.name in ("privacy.html",) or target.parent.name == "data":
                        continue   # shipped with the app, not built here
                    self.assertTrue(target.exists(), f"{f}: {href}")
                else:
                    self.assertTrue((target / "index.html").exists(), f"{f}: {href}")

    def test_article_photos(self):
        import tomllib
        from seo.photos import DIR
        chosen = {k for k, v in tomllib.loads((CONTENT / "photos.toml").read_text(encoding="utf-8")).items() if v.get("file")}
        for a in self.articles:   # every photo an article names is chosen in photos.toml
            with self.subTest(article=a.path):
                for k in [a.meta.get("image"), *a.meta.get("images", [])]:
                    if k:
                        self.assertIn(k, chosen)
        if not (DIR / "photos.json").exists():
            self.skipTest("no photos fetched yet (article-photos workflow, mode=fetch)")
        credits = json.loads((DIR / "photos.json").read_text(encoding="utf-8"))
        for k, c in credits.items():   # credited, freely licensed, and on disk
            with self.subTest(photo=k):
                self.assertTrue(c["author"] and c["page"].startswith("https://commons.wikimedia.org/"))
                self.assertNotRegex(c["license"], r"NC|ND")
                self.assertTrue((DIR / f"{k}.webp").exists() and (DIR / f"{k}-600.webp").exists())
        html = (self.tmp / "durga-puja/rituals/ashtami/index.html").read_text(encoding="utf-8")
        self.assertIn('class="photo hero"', html)
        self.assertIn("via Wikimedia Commons", html)
        self.assertGreaterEqual(html.count('<figure class="photo'), 3)   # hero + two between sections
        p = Page()
        p.feed(html)
        main = next(x for x in p.ld if x.get("@type") == "Article")
        self.assertEqual(main["image"][0]["@type"], "ImageObject")
        self.assertIn("license", main["image"][0])
        self.assertIn("img/guide/pushpanjali.webp", (self.tmp / "sitemap.xml").read_text(encoding="utf-8"))

    def test_directory_timelines_and_step_photos(self):
        html = (self.tmp / "guides/index.html").read_text(encoding="utf-8")
        p = Page()
        p.feed(html)
        self.assertEqual(p.canonical, self.base + "guides/")
        coll = next(x for x in p.ld if x.get("@type") == "CollectionPage")
        self.assertEqual(coll["mainEntity"]["numberOfItems"], len([a for a in self.articles if a.path != "durga-puja/"]))
        for a in self.articles:   # every guide is in the directory
            if a.path != "durga-puja/":
                self.assertIn(f"href='../{a.path}'", html)
        self.assertIn("The five days, day by day", html)
        self.assertIn('href="../../../guides/"', (self.tmp / "durga-puja/rituals/ashtami/index.html").read_text(encoding="utf-8"))   # in the menu
        hist = (self.tmp / "durga-puja/history/index.html").read_text(encoding="utf-8")
        self.assertIn("class='timeline'", hist)
        self.assertIn("1757", hist)
        self.assertIn("## At a glance", (self.tmp / "durga-puja/history/index.md").read_text(encoding="utf-8"))
        home = (self.tmp / "durga-puja/at-home/index.html").read_text(encoding="utf-8")
        from seo.photos import DIR
        if (DIR / "photos.json").exists():
            self.assertIn("step-photo", home)

    def test_photo_stories(self):
        d = self.tmp / "stories"
        if not d.exists():
            self.skipTest("no photos fetched yet")
        sitemap = (self.tmp / "sitemap.xml").read_text(encoding="utf-8")
        for f in sorted(d.glob("*/index.html")):
            with self.subTest(story=f.parent.name):
                html = f.read_text(encoding="utf-8")
                for must in ('<html ⚡ lang="en">', "<style amp-boilerplate>", "https://cdn.ampproject.org/v0/amp-story-1.0.js", "<amp-story standalone",
                             'publisher-logo-src="https://', 'poster-portrait-src="https://', f'<link rel="canonical" href="{self.base}stories/{f.parent.name}/">'):
                    self.assertIn(must, html)
                self.assertNotRegex(html, r"<img |<script>| style=")   # AMP: amp-img only, no inline script or style attributes
                self.assertGreaterEqual(html.count("<amp-story-page "), 6)
                self.assertIn("Wikimedia Commons", html)
                self.assertLess(len(re.search(r"<style amp-custom>(.*?)</style>", html, re.S).group(1).encode()), 75000)
                for href in re.findall(r'href="(\.\./[^"]*)"', html):   # links back to the guides resolve
                    if not href.endswith((".svg", ".png")):
                        self.assertTrue((f.parent / href / "index.html").resolve().exists(), href)
                self.assertIn(f"{self.base}stories/{f.parent.name}/", sitemap)
        self.assertIn("class='story-link'", (self.tmp / "durga-puja/rituals/ashtami/index.html").read_text(encoding="utf-8"))
        self.assertIn("story-cards", (self.tmp / "stories/index.html").read_text(encoding="utf-8"))

    def test_articles(self):
        self.assertGreater(len(self.articles), 0)
        for a in self.articles:
            with self.subTest(article=a.path):
                self.assertTrue(45 <= len(a.title) <= 110, a.title)
                self.assertTrue(110 <= len(a.desc) <= 200, f"{len(a.desc)}: {a.desc}")
                self.assertTrue(len(a.summary.split()) >= 25, "summary should answer the question in a few sentences")
                md = (self.tmp / a.path / "index.md").read_text(encoding="utf-8")
                self.assertTrue(md.startswith(f"# {a.h1}"))
                html = (self.tmp / a.path / "index.html").read_text(encoding="utf-8")
                self.assertIn('rel="alternate" type="text/markdown"', html)
                if a.meta.get("type") == "Recipe":
                    self.assertIn('"@type":"Recipe"', html)
                    self.assertIn('"recipeIngredient"', html)
                    self.assertIn('"recipeInstructions"', html)
                elif a.meta.get("steps"):
                    self.assertIn('"@type":"HowTo"', html)
                if a.meta.get("terms"):
                    self.assertIn('"@type":"DefinedTermSet"', html)
                for f in a.meta.get("faq", []):
                    self.assertTrue(f["q"].strip().endswith("?"), f["q"])
        # hubs list their section
        hub = (self.tmp / "durga-puja" / "rituals" / "index.html")
        if hub.exists():
            self.assertIn("In this section", hub.read_text(encoding="utf-8"))

    def test_404_manifest_and_images(self):
        self.assertIn("noindex", (self.tmp / "404.html").read_text(encoding="utf-8"))
        manifest = json.loads((self.tmp / "seo-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest), self.n)
        sm = (self.tmp / "sitemap.xml").read_text(encoding="utf-8")
        self.assertIn("<image:loc>", sm)

    def test_site_pages_and_tools(self):
        for p in ("about/", "contact/", "terms/", "search/", "tools/bijoya-card/"):
            self.assertTrue((self.tmp / p / "index.html").exists(), p)
        self.assertIn("noindex", (self.tmp / "search" / "index.html").read_text(encoding="utf-8"))
        idx = json.loads((self.tmp / "guide" / "search-index.json").read_text(encoding="utf-8"))
        self.assertGreater(len(idx), 300)
        self.assertNotIn("&amp;", json.dumps(idx, ensure_ascii=False))
        ics = (self.tmp / f"durga-puja-{self.g['meta']['year']}.ics").read_bytes().decode("utf-8")
        self.assertEqual(ics.count("BEGIN:VEVENT"), len(self.g["meta"]["days"]))
        self.assertTrue(all(len(line.encode()) <= 75 for line in ics.split("\r\n")))
        # No AdSense unless site.json says so
        self.assertFalse((self.tmp / "ads.txt").exists())
        self.assertNotIn("adsbygoogle", (self.tmp / "guide" / "index.html").read_text(encoding="utf-8"))
        for a in self.articles:
            if a.type == "Recipe":
                html = (self.tmp / a.path / "index.html").read_text(encoding="utf-8")
                self.assertIn('"@type":"Recipe"', html)
                self.assertIn('"recipeIngredient"', html)

    def test_adsense_switch(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            shutil.copy(ROOT / "app" / "index.html", tmp / "index.html")
            build_seo.Site(self.g, self.base, tmp, adsense="ca-pub-1234567890123456").build()
            self.assertEqual((tmp / "ads.txt").read_text(), "google.com, pub-1234567890123456, DIRECT, f08c47fec0942fa0\n")
            self.assertIn("adsbygoogle.js?client=ca-pub-1234567890123456", (tmp / "durga-puja" / "index.html").read_text(encoding="utf-8"))
            self.assertNotIn("adsbygoogle", (tmp / "about" / "index.html").read_text(encoding="utf-8"))   # no ads on site pages
            home = (tmp / "index.html").read_text(encoding="utf-8")
            self.assertIn('name="google-adsense-account"', home)
            self.assertNotIn("adsbygoogle", home)   # the app stays ad-free
        finally:
            shutil.rmtree(tmp)

    def test_markdown_renderer(self):
        r = render("Intro with **bold**, *it* and [a link](/durga-puja/history/).\n\n## First part\n\n- one\n- two\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n> ॐ line one\n> line two\n\n1. step\n2. step", up="../../")
        self.assertIn('<a href="../../durga-puja/history/">a link</a>', r.html)
        self.assertIn("<strong>bold</strong>", r.html)
        self.assertIn("<em>it</em>", r.html)
        self.assertIn('<h2 id="first-part">', r.html)
        self.assertIn("<ul><li>one</li><li>two</li></ul>", r.html)
        self.assertIn("<td>1</td>", r.html)
        self.assertIn('<blockquote class="verse"><p>ॐ line one<br>line two</p></blockquote>', r.html)   # a mantra block
        self.assertIn("<ol><li>step</li><li>step</li></ol>", r.html)
        self.assertEqual(r.links, ["durga-puja/history/"])
        self.assertEqual(r.toc, [("first-part", "First part")])
        self.assertNotIn("<script", render("<script>alert(1)</script>").html)
        c = render("- [ ] Water\n- [x] Shoes").html
        self.assertIn('<ul class="checklist">', c)
        self.assertEqual(c.count('type="checkbox"'), 2)
        t = render("> **Tip:** Go *early*.\n\n> Plain words").html
        self.assertIn('<aside class="callout tip">', t)
        self.assertIn("<em>early</em>", t)
        self.assertIn("<blockquote><p>Plain words</p></blockquote>", t)
        f = render("![A dhaki](photo:dhaki)\n\n![Gone](photo:missing)", figure=lambda k, c: f"<figure>{k}:{c}</figure>" if k == "dhaki" else "").html
        self.assertIn("<figure>dhaki:A dhaki</figure>", f)
        self.assertNotIn("missing", f)

    def test_sitemap_and_crawler_files(self):
        sm = (self.tmp / "sitemap.xml").read_text(encoding="utf-8")
        locs = re.findall(r"<loc>([^<]+)</loc>", sm)
        self.assertEqual(len(locs), self.n + 1)
        for u in locs[1:]:
            self.assertTrue((self.tmp / u[len(self.base):] / "index.html").exists(), u)
        robots = (self.tmp / "robots.txt").read_text(encoding="utf-8")
        for bot in ("GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended"):
            self.assertIn(f"User-agent: {bot}\nAllow: /", robots)
        self.assertIn(f"Sitemap: {self.base}sitemap.xml", robots)
        llms = (self.tmp / "llms.txt").read_text(encoding="utf-8")
        self.assertTrue(llms.startswith("# Pujo Parikrama"))
        for a in self.articles:
            self.assertIn(f"{self.base}{a.path}index.md", llms)
        self.assertIn("\n> ", llms)
        for p in self.g["pandals"]:
            self.assertIn(f"{self.base}guide/pandals/{p['id']}/", llms)
        full = (self.tmp / "llms-full.txt").read_text(encoding="utf-8")
        self.assertIn(self.g["food"][0]["name"], full)

    def test_index_gets_a_static_summary(self):
        s = (self.tmp / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="seo-static"', s)
        self.assertIn('href="guide/"', s)
        self.assertEqual(s.count("<!--seo:start-->"), 1)
        # Building twice replaces the block instead of stacking it
        build_seo.Site(self.g, self.base, self.tmp).build()
        self.assertEqual((self.tmp / "index.html").read_text(encoding="utf-8").count('id="seo-static"'), 1)

    def test_facts_come_from_the_data(self):
        p = self.g["pandals"][0]
        s = (self.tmp / "guide" / "pandals" / p["id"] / "index.html").read_text(encoding="utf-8")
        self.assertIn(p["nearest_metro"]["name"], s)
        self.assertIn("estimates", s)   # crowd numbers are labelled as model estimates
        d = (self.tmp / "guide" / "dates" / "index.html").read_text(encoding="utf-8")
        for day in self.g["meta"]["days"]:
            self.assertIn(build_seo.nice_date(day["date"], True), d)


if __name__ == "__main__":
    unittest.main()
