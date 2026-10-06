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
        cls.pages = sorted(cls.tmp.glob("guide/**/index.html"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_one_page_per_place_area_and_trail(self):
        g = self.g
        want = len(g["pandals"]) + len(g["food"]) + len(g["zones"]) + len(g["itineraries"]) + 3  # hub, dates, parking
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

    def test_sitemap_and_crawler_files(self):
        sm = (self.tmp / "sitemap.xml").read_text(encoding="utf-8")
        locs = re.findall(r"<loc>([^<]+)</loc>", sm)
        self.assertEqual(len(locs), len(self.pages) + 1)
        for u in locs[1:]:
            self.assertTrue((self.tmp / u[len(self.base):] / "index.html").exists(), u)
        robots = (self.tmp / "robots.txt").read_text(encoding="utf-8")
        for bot in ("GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended"):
            self.assertIn(f"User-agent: {bot}\nAllow: /", robots)
        self.assertIn(f"Sitemap: {self.base}sitemap.xml", robots)
        llms = (self.tmp / "llms.txt").read_text(encoding="utf-8")
        self.assertTrue(llms.startswith("# Pujo Parikrama"))
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
