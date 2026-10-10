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
from marketing.captions import compose

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


class BatchTest(unittest.TestCase):
    """Instagram batch files: every item resolves, captions fit Instagram's limits, never the github.io address."""

    def test_batches(self):
        from marketing import carousels, publish_batch
        with tempfile.TemporaryDirectory() as tmp:
            spec = carousels.build(tmp)
        for f in sorted((Path(__file__).resolve().parents[1] / "marketing" / "batches").glob("*.json")):
            items = json.loads(f.read_text(encoding="utf-8"))["items"]
            self.assertTrue(items, f)
            seen = set()
            for item in items:
                p = publish_batch.resolve(item, spec)
                key = (p["kind"], p["label"])
                self.assertNotIn(key, seen, f"{f.name}: {key} twice")
                seen.add(key)
                self.assertTrue(all(u.startswith("https://") for u in p["urls"]), key)
                self.assertTrue(2 <= len(p["urls"]) <= 10 if p["kind"] == "carousel" else len(p["urls"]) == 1, key)
                self.assertLessEqual(len(p["caption"]), 2200, key)
                self.assertLessEqual(p["caption"].count("#"), 30, key)
                self.assertNotIn("github.io", p["caption"], key)


class AlreadyPostedTest(unittest.TestCase):
    """A late or repeated daily run must not post the same kit twice."""

    def run_with(self, media):
        from unittest import mock
        from marketing import publish_ig
        cards = [{"format": "post", "caption_en": "Ma ashchhen! Plan your pujo", "caption_bn": "মা আসছেন"},
                 {"format": "story"}]
        with mock.patch.object(publish_ig, "graph", return_value={"data": media}):
            return publish_ig.already_posted(cards, "1", "IGtoken")

    def ts(self, hours_ago):
        return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%S+0000")

    def test_same_caption_today_is_a_repeat(self):
        self.assertTrue(self.run_with([{"caption": "Ma ashchhen! Plan your pujo\n\nমা আসছেন", "timestamp": self.ts(2)}]))

    def test_other_or_old_posts_are_not(self):
        self.assertFalse(self.run_with([{"caption": "Something else", "timestamp": self.ts(1)},
                                        {"caption": "Ma ashchhen! Plan your pujo\n\nমা আসছেন", "timestamp": self.ts(60)},
                                        {"timestamp": self.ts(1)}]))


class DailySetTest(unittest.TestCase):
    """Daily reels: every plan is renderable, and a day posts only once it is approved."""

    def test_plans_are_valid(self):
        from marketing.footage import factory
        idx = factory.footage_index(None)
        for p in sorted((Path(__file__).resolve().parents[1] / "marketing" / "daily").glob("2*.json")):
            plan = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(plan["date"], p.stem)
            ids = [i["id"] for i in plan["items"]]
            self.assertEqual(len(ids), len(set(ids)), p.name)
            for it in plan["items"]:
                self.assertRegex(it["at"], r"^\d\d:\d\d$")
                self.assertIn(it["type"], ("reel", "story", "photo"))
                if it["type"] == "photo":  # words over hashtags: a real caption, a handful of tags
                    cap = it["caption"]
                    self.assertGreater(len(cap["en"]), 200, it["id"])
                    self.assertLessEqual(cap["tags"].count("#"), 5, it["id"])
                    self.assertNotIn("github.io", cap.get("bn", "") + cap["en"])
                if it["type"] == "reel":
                    text = compose(it.get("caption"))
                    self.assertLessEqual(len(text), 2200, it["id"])
                    self.assertLessEqual(text.count("#"), 25, it["id"])
                    self.assertNotIn("github.io", text)
            known = {s[0] for it in plan["items"] for s in it.get("segments", [])} - set(idx)
            if not known:  # catalogue clips are checked by the factory itself, which has the catalogue
                factory.check(plan, idx)

    def test_unapproved_day_is_a_dry_run(self):
        from unittest import mock
        from marketing import publish_batch
        items = {"items": [{"type": "story", "id": "x", "at": "10:30", "video_url": "https://e/x.mp4"},
                           {"type": "reel", "id": "y", "at": "18:30", "video_url": "https://e/y.mp4", "caption": "c"}]}
        with mock.patch.object(publish_batch, "get_json", return_value=items), \
             mock.patch.object(publish_batch, "approved", return_value=False), \
             mock.patch.object(publish_batch, "reachable", return_value=True), \
             mock.patch.object(publish_batch, "publish") as pub, \
             mock.patch.dict("os.environ", {"IG_USER_ID": "1", "IG_ACCESS_TOKEN": "IGx"}):
            publish_batch.main(["--date", "2026-10-06", "--window", "pm"])
        pub.assert_not_called()

    def test_failed_item_does_not_block_later_slots(self):
        from unittest import mock
        from marketing import publish_batch
        items = {"items": [{"type": "story", "id": "s3", "at": "20:00", "video_url": "https://e/s3.mp4"},
                           {"type": "reel", "id": "r3", "at": "21:00", "video_url": "https://e/r3.mp4", "caption": "c"}]}
        tries = []

        def once(p, user, token):
            tries.append(p["label"])
            if p["label"] == "s3":
                raise publish_batch.NotProcessed("Instagram could not process container 1 (ERROR)")
            return "m1"
        with mock.patch.object(publish_batch, "get_json", return_value=items), \
             mock.patch.object(publish_batch, "approved", return_value=True), \
             mock.patch.object(publish_batch, "reachable", return_value=True), \
             mock.patch.object(publish_batch, "publish_once", side_effect=once), \
             mock.patch.object(publish_batch, "wait_until"), mock.patch.object(publish_batch.time, "sleep"), \
             mock.patch.dict("os.environ", {"IG_USER_ID": "1", "IG_ACCESS_TOKEN": "IGx"}):
            with self.assertRaises(SystemExit) as e:
                publish_batch.main(["--date", "2026-10-08", "--window", "pm"])
        self.assertEqual(tries, ["s3", "s3", "r3"])  # one fresh container for the story, then the reel still posts
        self.assertIn("[1]", str(e.exception))


class RedesignTest(unittest.TestCase):
    """Real-photo redesign: every slide finds a photo, Wave 1 keeps its words, voiceover reels line up."""

    @classmethod
    def setUpClass(cls):
        cls.g = json.loads((Path(__file__).resolve().parents[1] / "app" / "data" / "guide.json").read_text(encoding="utf-8"))

    def test_every_carousel_slide_gets_a_photo(self):
        from marketing import carousels, photos
        lib = photos.Library(self.g)
        for i, c in enumerate(carousels.Carousels(self.g).all()):
            lib.dress(c["slides"], "unused", seed=i, fetch=False)
            heroes = [s.get("photo") for s in c["slides"]]
            self.assertTrue(all(heroes), c["id"])
            self.assertEqual(len(heroes), len(set(heroes)), f"{c['id']} repeats a photo")

    def test_topics_match_whole_words(self):
        from marketing import photos
        lib = photos.Library(self.g)
        self.assertEqual(lib.topical("Metro cheat sheet"), [])          # "eat" inside "cheat" is not food
        self.assertRegex(lib.topical("Sindoor khela on Dashami")[0]["label"].lower(), "sindoor|boron|bijoya|dashami")

    def test_wave1_keeps_every_line(self):
        from marketing import posts
        spec = json.loads(posts.SPEC.read_text(encoding="utf-8"))
        for p in spec["posts"]:
            new = json.dumps(posts.convert(p), ensure_ascii=False)
            for s in p["slides"]:
                for k in ("bn", "en", "tr"):
                    if s.get(k):
                        self.assertIn(json.dumps(s[k], ensure_ascii=False)[1:-1], new, f"{p['id']} lost {k}")

    def test_voiceover_needs_a_line_per_shot(self):
        from marketing.footage import factory
        plan = {"items": [{"id": "r1", "type": "reel", "segments": [["f15", 0, 3, ""], ["f15", 4, 3, ""]],
                           "vo": {"lines": ["এক"], "urls": ["https://e/1.mp3"]}}]}
        with self.assertRaises(SystemExit):
            factory.check(plan, factory.footage_index(None))
        plan["items"][0]["vo"] = {"lines": ["এক", "দুই"], "urls": ["https://e/1.mp3", "https://e/2.mp3"]}
        factory.check(plan, factory.footage_index(None))

    @unittest.skipUnless(__import__("importlib.util").util.find_spec("PIL"), "the reel builder needs Pillow")
    def test_fit_start_keeps_cuts_inside_the_clip(self):
        from marketing.reels import build2
        fx = {"c": {"dur": 10.0}}
        self.assertEqual(build2.fit_start(fx, "c", 8, 4), 5.9)
        self.assertEqual(build2.fit_start(fx, "c", 2, 4), 2)
        self.assertEqual(build2.fit_start({}, "x", 7, 4), 7)

    @unittest.skipUnless(__import__("importlib.util").util.find_spec("PIL") and __import__("shutil").which("ffmpeg"),
                         "needs Pillow and ffmpeg")
    def test_photo_move_is_smooth_and_full_length(self):
        import subprocess, tempfile
        from PIL import Image
        from marketing.reels import build2
        with tempfile.TemporaryDirectory() as d:
            Image.new("RGB", (1300, 2300), (120, 40, 30)).save(f"{d}/p.jpg")
            build2.still(f"{d}/p.jpg", f"{d}/s.jpg", 0.5, 0.45)
            out = build2.still_motion(f"{d}/s.jpg", f"{d}/m.mp4", 1.0, 0)
            n = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v", "-show_entries",
                                "stream=nb_read_frames,width,height", "-of", "csv=p=0", out], capture_output=True, text=True).stdout
            self.assertEqual(n.strip(), f"{build2.W},{build2.H},{build2.FPS}")
        self.assertGreaterEqual(build2.MIN_SHOT, 5.0)
        self.assertGreater(build2.ease(0.5), build2.ease(0.1))
        self.assertEqual((build2.ease(0), build2.ease(1)), (0, 1))

    @unittest.skipUnless(__import__("importlib.util").util.find_spec("PIL"), "needs Pillow")
    def test_cinematic_look_conforms_to_24fps_and_frames_small_footage(self):
        from marketing.reels import build2
        self.assertEqual(build2.conform(30), 0.8)  # every source frame becomes one 24 fps frame
        self.assertEqual(build2.conform(60), 0.4)
        self.assertEqual(build2.conform(25), 1.0)
        self.assertTrue(build2.cine({}) and not build2.cine({"style": "classic"}))
        fx = {"hd": {"w": 1920, "h": 1080}, "uhd": {"w": 3840, "h": 2160}, "tall": {"w": 1080, "h": 1920}}
        src = lambda d, sid: f"{sid}.mp4"
        real = build2.src_file
        build2.src_file = src
        try:
            self.assertEqual(build2.frame_for({"segments": [["uhd", 0, 3, ""], ["tall", 0, 3, ""]]}, fx, "."), "full")
            self.assertEqual(build2.frame_for({"segments": [["uhd", 0, 3, ""], ["hd", 0, 3, ""]]}, fx, "."), "window")
        finally:
            build2.src_file = real

    @unittest.skipUnless(__import__("importlib.util").util.find_spec("PIL"), "needs Pillow")
    def test_photo_post_is_4x5_and_credits_every_photographer(self):
        import tempfile
        from PIL import Image
        from marketing.footage import photo_post
        it = {"id": "p1", "type": "photo", "caption": {"bn": "মা", "en": "Maa", "tags": "#DurgaPuja2026"},
              "photos": [{"src": "https://e/a.jpg", "artist": "A", "license": "CC BY 3.0"},
                         {"src": "https://e/b.jpg", "artist": "B", "license": "CC BY-SA 4.0"},
                         {"src": "https://e/c.jpg", "license": "AI"}]}
        self.assertEqual(photo_post.check(it), [])
        self.assertTrue(photo_post.check(dict(it, photos=[{"src": "https://e/x.jpg"}])))
        cap = photo_post.caption(it)  # credits are on the photos, not in the caption
        self.assertNotIn("CC BY", cap)
        self.assertEqual(photo_post.credit_line(it["photos"][0]), "Photo: A · CC BY 3.0")
        self.assertEqual(photo_post.credit_line(it["photos"][2]), "AI image")
        with tempfile.TemporaryDirectory() as d:
            Image.new("RGB", (3000, 2000), (200, 30, 40)).save(f"{d}/l.jpg")
            photo_post.crop(f"{d}/l.jpg", f"{d}/o.jpg", 0.9, 0.5, "Photo: A · CC BY 3.0")
            self.assertEqual(Image.open(f"{d}/o.jpg").size, (photo_post.PW, photo_post.PH))

    def test_engagement_creators_and_replies(self):
        import io, contextlib, tempfile
        from marketing import engage
        cs = json.loads(engage.CREATORS.read_text(encoding="utf-8"))["creators"]
        self.assertTrue(cs)
        for c in cs:
            self.assertRegex(c["handle"], r"^[A-Za-z0-9_.]{1,30}$")
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"replies": [{"comment_id": "1", "text": "ধন্যবাদ", "approved": True},
                                   {"comment_id": "2", "text": "not yet", "approved": False}]}, f)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            engage.reply(f.name, dry=True)  # only approved replies, and a dry run needs no token
        self.assertIn("reply to 1", out.getvalue())
        self.assertNotIn("reply to 2", out.getvalue())

    def test_comment_keyword_for_the_dm(self):
        from marketing import engage
        for t in ("PUJO", "pujo pls 🙏", "পুজো", "Route?"):
            self.assertTrue(engage.wants_guide(t), t)
        for t in ("beautiful", "", None, "Durga maa 🙏"):
            self.assertFalse(engage.wants_guide(t), t)
        self.assertIn("pujoparikramaguide.in", engage.GUIDE)
        self.assertNotIn("github.io", engage.DM_EN + engage.GUIDE)
        cfg = json.loads((Path(__file__).resolve().parents[1] / "marketing/engage/config.json").read_text(encoding="utf-8"))
        self.assertIn("dm", cfg)

    def test_creator_clip_needs_permission(self):
        from marketing.footage import factory
        idx = factory.footage_index(None)
        idx["cr-x"] = dict(source="Instagram", url="https://e/x.mp4", dur=20, artist="@x", license="used with permission", permission="")
        plan = {"items": [{"id": "r1", "type": "reel", "segments": [["cr-x", 0, 3, ""]]}]}
        with self.assertRaises(SystemExit):
            factory.check(plan, idx)
        idx["cr-x"]["permission"] = "2026-10-07, Instagram DM"
        factory.check(plan, idx)

    @unittest.skipUnless(__import__("importlib.util").util.find_spec("PIL"), "needs Pillow")
    def test_card_carousel_has_our_words_on_every_slide(self):
        import tempfile
        from PIL import Image
        from marketing import cards
        it = {"id": "p3", "type": "photo", "render": "cards", "caption": {"en": "Durga Puja 2026 themes"},
              "slides": [{"t": "cover", "title": ["2026 THEMES"], "photo": {"src": "https://e/a.jpg", "artist": "A", "license": "CC BY 3.0"}},
                         {"t": "item", "kicker": "1/1", "name": "Behala Notun Dal", "title": "Ay Aaro Bendhe Bendhe Thaki",
                          "body": "A Shankha Ghosh poem.", "foot": "Nearest station: Behala Bazar · 2 min walk"},
                         {"t": "end", "title": ["SEND THIS", "TO YOUR PUJO GROUP"]}]}
        self.assertEqual(cards.check(it), [])
        self.assertTrue(cards.check(dict(it, slides=it["slides"][:1])))  # one slide is not a carousel
        self.assertTrue(cards.check(dict(it, slides=[{"t": "photo", "title": "x"}, it["slides"][2]])))  # photo slide, no photo
        with tempfile.TemporaryDirectory() as d:
            names = cards.build(it, "x", d, d, lambda src, dest: Image.new("RGB", (900, 700)).save(dest))
            self.assertEqual(len(names), 3)
            self.assertEqual(Image.open(f"{d}/{names[1]}").size, (1440, 1800))

    def test_caption_layout_is_english_first_keywords_then_three_tags(self):
        from marketing.captions import compose
        c = {"en": "Durga Puja 2026 in Kolkata: one route a night.", "bn": "এক রাতে এক এলাকা",
             "keywords": ["durga puja 2026", "kolkata pandal hopping"], "tags": "#a #b #c #d #e"}
        self.assertEqual(compose(c), "Durga Puja 2026 in Kolkata: one route a night.\n\nএক রাতে এক এলাকা\n\n"
                                     "(durga puja 2026, kolkata pandal hopping)\n\n#a #b #c")
        self.assertEqual(compose("as is"), "as is")
        self.assertEqual(compose(None), "")

    def test_caption_lint_from_the_ig_skills(self):
        from marketing import caption_lint
        two_asks = "পুজোর রুট 🙏\n\nComment PUJO for the Durga Puja Kolkata routes. Save this for later.\n\n#DurgaPuja2026"
        notes = caption_lint.caption_notes(two_asks)
        self.assertTrue(any("one ask" in n for n in notes), notes)
        self.assertFalse(any("hashtags" in n for n in notes), notes)
        six = "Durga Puja in Kolkata, one route a night.\n\n#a1 #a2 #a3 #a4 #a5 #a6"
        self.assertTrue(any(n.startswith("FAIL hashtags") for n in caption_lint.caption_notes(six)))
        self.assertRegex(caption_lint.hook_note("In 1976, Bengal switched on the radio and got a shock"), r"^hook \d+ (STRONG|OK|WEAK)")
        self.assertEqual(caption_lint.caption_notes(""), [])

    @unittest.skipUnless(__import__("importlib.util").util.find_spec("PIL"), "the route reel needs Pillow")
    def test_route_reel_draws_the_guide_route(self):
        from marketing import route_reel
        pl = route_reel.plan("south_lakemarket")
        self.assertEqual(len(pl["xy"]), len(pl["order"]) + (1 if pl["station"] else 0))
        self.assertAlmostEqual(pl["km"][-1], pl["route"]["walk_m"] / 1000, places=1)
        self.assertEqual(pl["km"], sorted(pl["km"]))
        x0, y0, x1, y1 = route_reel.MAP
        for x, y in pl["xy"]:  # every stop inside the map, clear of the action rail and the caption
            self.assertTrue(x0 <= x <= x1 and y0 <= y <= y1)
        im = route_reel.frame(route_reel.backdrop(pl), pl, pl["t_hold"] - 0.1)
        self.assertEqual(im.size, (route_reel.W, route_reel.H))
        cap = route_reel.caption({"en": "English", "keywords": ["durga puja 2026"], "tags": "#DurgaPuja2026"})
        self.assertNotIn("Sumita Roy Dutta", cap)  # the dhak credit is on the end frame
        self.assertEqual(cap, "English\n\n(durga puja 2026)\n\n#DurgaPuja2026")
