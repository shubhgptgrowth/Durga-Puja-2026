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
        self.assertEqual(self.n, want)
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
                    self.assertTrue(types & {"Article", "HowTo"}, types)

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
                if target.suffix in (".txt", ".html", ".json", ".xml"):
                    if target.name in ("privacy.html",) or target.parent.name == "data":
                        continue   # shipped with the app, not built here
                    self.assertTrue(target.exists(), f"{f}: {href}")
                else:
                    self.assertTrue((target / "index.html").exists(), f"{f}: {href}")

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
                if a.meta.get("steps"):
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

    def test_markdown_renderer(self):
        r = render("Intro with **bold**, *it* and [a link](/durga-puja/history/).\n\n## First part\n\n- one\n- two\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n> ॐ line one\n> line two\n\n1. step\n2. step", up="../../")
        self.assertIn('<a href="../../durga-puja/history/">a link</a>', r.html)
        self.assertIn("<strong>bold</strong>", r.html)
        self.assertIn("<em>it</em>", r.html)
        self.assertIn('<h2 id="first-part">', r.html)
        self.assertIn("<ul><li>one</li><li>two</li></ul>", r.html)
        self.assertIn("<td>1</td>", r.html)
        self.assertIn("<blockquote><p>ॐ line one<br>line two</p></blockquote>", r.html)
        self.assertIn("<ol><li>step</li><li>step</li></ol>", r.html)
        self.assertEqual(r.links, ["durga-puja/history/"])
        self.assertEqual(r.toc, [("first-part", "First part")])
        self.assertNotIn("<script", render("<script>alert(1)</script>").html)

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
