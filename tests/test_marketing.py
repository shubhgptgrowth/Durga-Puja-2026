"""Content kit checks: every campaign day has cards, captions in both languages, and tracked links
that the backend's source cleaner accepts (otherwise the reach report would bucket them as 'other')."""
import datetime as dt
import json
import re
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from marketing import kit

SRC_OK = re.compile(r"^[a-z0-9_]{1,40}$")  # same rule as public._clean_src in supabase/migrations


class KitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        stats = [{"place_id": "sreebhumi", "today": 900, "visits": 1000}, {"place_id": "tala_prattoy", "today": 700, "visits": 800},
                 {"place_id": "suruchi_sangha", "today": 500, "visits": 600}]
        cls.bundle = kit.build(cls.tmp.name, dt.date(2026, 10, 19), {r["place_id"]: r for r in stats})
        cls.out = Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_day_has_a_post_and_a_story(self):
        d = kit.START
        while d <= kit.END:
            day = json.loads((self.out / d.isoformat() / "assets.json").read_text(encoding="utf-8"))
            fmts = {c["format"] for c in day["cards"]}
            self.assertTrue({"post", "story"} <= fmts, d)
            self.assertIn("wa_channel", day["whatsapp"]["channel"])
            self.assertIn("wa_fwd", day["whatsapp"]["forward"])
            d += dt.timedelta(days=1)

    def test_captions_are_bilingual_and_tagged(self):
        for c in self.bundle["cards"]:
            self.assertTrue(re.search(r"[ঀ-৿]", c["caption_bn"]), c["id"])
            self.assertIn("#DurgaPuja2026", c["caption_en"])
            self.assertLess(len(c["caption_en"]), 2200, "Instagram caption limit")

    def test_tracked_links_use_valid_source_codes(self):
        urls = [c["link"] for c in self.bundle["cards"]] + [p["url"] for p in self.bundle["posters"]] + [self.bundle["flyer"]["url"]]
        for u in urls:
            q = parse_qs(urlparse(u).query)
            self.assertTrue(u.startswith(kit.SITE), u)
            self.assertRegex(q["src"][0], SRC_OK, u)

    def test_posters_deep_link_to_real_places(self):
        g = json.loads((kit.ROOT / "app" / "data" / "guide.json").read_text(encoding="utf-8"))
        ids = {p["id"] for p in g["pandals"]} | {f["id"] for f in g["food"]}
        for p in self.bundle["posters"]:
            self.assertIn(urlparse(p["url"]).fragment[2:], ids)

    def test_live_day_uses_todays_check_ins(self):
        day = json.loads((self.out / "2026-10-19" / "assets.json").read_text(encoding="utf-8"))
        post = next(c for c in day["cards"] if c["format"] == "post")
        self.assertIn("trending", post["id"])
        self.assertEqual(post["data"]["items"][0]["name"], "Sreebhumi Sporting Club")
        other = json.loads((self.out / "2026-10-18" / "assets.json").read_text(encoding="utf-8"))
        self.assertIn("quiet", other["cards"][0]["id"], "other days fall back to best-time cards")

    def test_card_files_are_unique(self):
        files = [c["file"] for c in self.bundle["cards"]]
        self.assertEqual(len(files), len(set(files)))

    def test_kit_page_lists_every_day(self):
        page = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertEqual(page.count('class="day"'), (kit.END - kit.START).days + 1)
        self.assertIn('name="robots" content="noindex"', page)



class CarouselTest(unittest.TestCase):
    """Instagram carousels: enough of them, the right shape, bilingual captions, and never the github.io address."""

    @classmethod
    def setUpClass(cls):
        from marketing import carousels
        cls.tmp = tempfile.TemporaryDirectory()
        cls.spec = carousels.build(cls.tmp.name)
        cls.out = Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_shape(self):
        cs = self.spec["carousels"]
        self.assertGreaterEqual(len(cs), 14)
        for c in cs:
            self.assertTrue(6 <= len(c["slides"]) <= 10, c["id"])
            self.assertEqual(c["slides"][0]["t"], "cover")
            self.assertEqual(c["slides"][-1]["t"], "cta")
            self.assertTrue(8 <= len(c["hashtags"].split()) <= 12, c["id"])
            self.assertRegex(c["caption_bn"], "[ঀ-৿]")
            self.assertTrue((self.out / c["id"] / "caption.txt").exists())
        self.assertTrue((self.out / "index.md").exists())

    def test_no_site_address(self):
        text = (self.out / "carousels.json").read_text(encoding="utf-8") + (self.out / "index.md").read_text(encoding="utf-8")
        self.assertNotIn("github.io", text)

if __name__ == "__main__":
    unittest.main()


class ContactsSummaryTest(unittest.TestCase):
    def test_summary_is_counts_only(self):
        from marketing.contacts import summary_md
        md = summary_md({"contacts": 2, "new_today": 1, "withdrawn": 1, "by_source": {"ig_bio": 2}, "by_lang": {"bn": 2}})
        self.assertIn("**2** people", md)
        self.assertIn("Instagram bio link", md)
        self.assertNotRegex(md, r"\+91|\d{10}")
