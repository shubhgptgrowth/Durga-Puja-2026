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

    def test_held_item_is_not_posted(self):
        import json, tempfile
        from pathlib import Path
        from unittest import mock
        from marketing import publish_batch
        items = {"items": [{"type": "reel", "id": "1006-r1", "at": "14:00", "video_url": "https://e/r1.mp4", "caption": "c"},
                           {"type": "reel", "id": "1006-rv", "at": "15:00", "video_url": "https://e/rv.mp4", "caption": "c"}]}
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "approved.txt").write_text("2026-10-06\n")
            (Path(d) / "2026-10-06.json").write_text(json.dumps({"items": [{"id": "r1"}, {"id": "rv", "hold": True}]}))
            with mock.patch.object(publish_batch, "APPROVED", Path(d) / "approved.txt"), \
                 mock.patch.object(publish_batch, "get_json", return_value=items), \
                 mock.patch.object(publish_batch, "reachable", return_value=True), \
                 mock.patch.object(publish_batch, "publish_once", return_value="m1") as pub, \
                 mock.patch.object(publish_batch, "wait_until"), mock.patch.object(publish_batch.time, "sleep"), \
                 mock.patch.dict("os.environ", {"IG_USER_ID": "1", "IG_ACCESS_TOKEN": "IGx"}):
                publish_batch.main(["--date", "2026-10-06", "--window", "pm"])
        self.assertEqual([c.args[0]["label"] for c in pub.call_args_list], ["1006-r1"])

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
                publish_batch.main(["--date", "2026-10-08", "--window", "night"])
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

    def test_user_tags_sit_on_images_and_not_on_reels(self):
        import json as _j
        from marketing import publish_batch
        img = _j.loads(publish_batch.user_tags(["@durgapujakolkata", "durgopuja"]))
        self.assertEqual([t["username"] for t in img], ["durgapujakolkata", "durgopuja"])
        self.assertTrue(all(0 < t["x"] < 1 and 0 < t["y"] < 1 for t in img))
        self.assertEqual(_j.loads(publish_batch.user_tags(["a"], image=False)), [{"username": "a"}])

    def test_editorial_check_needs_meaning_for_mantras(self):
        from marketing import editorial
        it = {"id": "p1", "caption": {"en": "x"}, "slides": [{"t": "cover", "title": "T"}, {"t": "mantra", "text": "ॐ"}]}
        self.assertTrue(any("meaning" in e for e in editorial.check(it)))
        it["slides"][1]["meaning"] = "Om"
        self.assertEqual(editorial.check(it), [])

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
        for t in ("PUJO", "pujo pls 🙏", "পুজো", "Route?", "Pujo!!", "#pujo", "send route please", "পুজো প্লিজ", "PUJO 2026",
                  "PUJO route for kolkata pls", "I want the pujo route", "pujo list please", "Pujo da", "পুজো রুট চাই",
                  "PUJO @rina.sen @amit_k @dada.99"):
            self.assertTrue(engage.wants_guide(t), t)
        # praise that mentions pujo is not a request (a real 12 Oct comment), nor is a sentence about routes
        for t in ("beautiful", "", None, "Durga maa 🙏", "পুরোনো কলকাতার পুজো 🙌❤️😍", "beautiful pujo",
                  "which route is best?", "pujojo", "পুজোর শুভেচ্ছা", "@pujo_lover", "@rina so beautiful pujo"):
            self.assertFalse(engage.wants_guide(t), t)
        self.assertIn("pujoparikramaguide.in", engage.GUIDE)
        self.assertNotIn("github.io", engage.DM_EN + engage.GUIDE)
        cfg = json.loads((Path(__file__).resolve().parents[1] / "marketing/engage/config.json").read_text(encoding="utf-8"))
        self.assertIn("dm", cfg)

    def test_dm_reads_every_post_in_the_window(self):
        # at 10+ posts a day the newest 25 covered two days: comments on older posts in the 7-day window were missed
        import io
        from unittest import mock
        from marketing import engage
        now = dt.datetime.now(dt.timezone.utc)
        ts = lambda h: (now - dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%S+0000")
        page1 = {"data": [{"id": f"m{i}", "timestamp": ts(i), "comments_count": 0, "permalink": "p"} for i in range(50)],
                 "paging": {"next": "https://graph.facebook.com/next"}}
        page2 = {"data": [{"id": "old", "timestamp": ts(80), "comments_count": 1, "permalink": "p"},
                          {"id": "too_old", "timestamp": ts(200), "comments_count": 1, "permalink": "p"}]}

        def graph(method, path, token, **kw):
            if path.endswith("/media"):
                return page1
            return {"data": [{"id": "c_" + path.split("/")[0], "text": "PUJO", "username": "u", "timestamp": ts(70)}]}
        with mock.patch.object(engage, "graph", graph), \
                mock.patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(page2).encode())):
            got, err = engage.own_comments("1", "t", me="me")
        self.assertIsNone(err)
        self.assertEqual([c["comment_id"] for c in got], ["c_old"])
        # a new "PUJO" on an older post (the 8 Oct route post, a week later) is still read when older posts are asked
        # for, and a comment older than Instagram's 7-day private-reply window is dropped
        def graph2(method, path, token, **kw):
            if path.endswith("/media"):
                return page1
            return {"data": [{"id": "new_" + path.split("/")[0], "text": "PUJO", "username": "u", "timestamp": ts(5)},
                             {"id": "stale_" + path.split("/")[0], "text": "PUJO", "username": "u", "timestamp": ts(190)}]}
        with mock.patch.object(engage, "graph", graph2), \
                mock.patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(page2).encode())):
            got, err = engage.own_comments("1", "t", me="me", post_days=30)
        self.assertEqual(sorted(c["comment_id"] for c in got), ["new_old", "new_too_old"])

    def test_edge_function_dm_matches_the_fallback(self):
        # supabase/functions/ig-dm is the main sender; marketing/engage.py `dm` is the fallback. Same words, same keywords.
        from marketing import engage
        ts = (Path(__file__).resolve().parents[1] / "supabase/functions/ig-dm/index.ts").read_text(encoding="utf-8")
        flat = re.sub(r"[\"']\s*\+\s*[\"']", "", ts)  # join the string literals split across lines
        for s in (engage.DM_BN, engage.DM_EN, engage.GUIDE, *engage.KEYWORDS):
            self.assertIn(s, flat, s[:30])
        for name, py in (("KEYWORDS", engage.KEYWORDS), ("FILLER", engage.FILLER)):
            ts_list = re.search(rf"const {name} = \[(.*?)\];", ts, re.S).group(1)
            self.assertEqual(re.findall(r"'([^']*)'", ts_list), list(py), name)
        self.assertNotIn("quiet", engage.DM_EN + flat)
        self.assertIn(engage.ALREADY, ts)

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
        from unittest import mock
        with mock.patch("marketing.basemap.draw", side_effect=OSError("offline")):  # no network in tests: paper map
            im = route_reel.frame(route_reel.backdrop(pl), pl, pl["t_hold"] - 0.1)
        self.assertEqual(im.size, (route_reel.W, route_reel.H))
        # a themed route: pandal ids and a title, starting at the nearest Metro, nearest-next order
        ids = ["ballygunge_cultural", "hindustan_park", "bosepukur_sitala", "66_pally"]
        th = route_reel.plan(None, ids=ids, title="South Art Route", hook="4 pandals. 3 km. One evening.")
        self.assertEqual(sorted(p["id"] for p in th["order"]), sorted(ids))
        self.assertIsNotNone(th["station"])
        self.assertEqual(th["line3"], "ONE EVENING.")
        self.assertGreater(th["walk_m"], 1000)
        self.assertEqual(len(th["labels"]), len(ids))
        self.assertEqual(route_reel.hook_line3(None), "ONE NIGHT.")
        self.assertEqual(route_reel.short_name({"name": "AE Block Salt Lake"}, "Salt Lake"), "AE Block")
        self.assertEqual(route_reel.short_name({"name": "Bagbazar Sarbojanin"}), "Bagbazar")
        with self.assertRaises(SystemExit):
            route_reel.plan(None, ids=["no_such_pandal"], title="x")
        cap = route_reel.caption({"en": "English", "keywords": ["durga puja 2026"], "tags": "#DurgaPuja2026"})
        self.assertNotIn("Sumita Roy Dutta", cap)  # the dhak credit is on the end frame
        self.assertEqual(cap, "English\n\n(durga puja 2026)\n\n#DurgaPuja2026")

    @unittest.skipUnless(__import__("importlib.util").util.find_spec("PIL"), "the night route reel needs Pillow")
    def test_night_route_reel_lights_the_guide_route(self):
        from unittest import mock
        from marketing import night_route
        pl = night_route.plan("north", area="North Kolkata", part=1, nxt="Central Kolkata", next_key="central")
        self.assertEqual(len(pl["xy"]), len(pl["order"]) + (1 if pl["station"] else 0))
        self.assertAlmostEqual(pl["km"][-1], pl["walk_m"] / 1000, places=1)
        x0, y0, x1, y1 = night_route.FIT
        for x, y in pl["xy"]:  # every stop under the header, clear of the action rail and the card
            self.assertTrue(x0 - 1 <= x <= x1 + 1 and y0 - 1 <= y <= y1 + 1)
        self.assertTrue(pl["lit"] and len(pl["lit"]) <= 5)
        self.assertTrue(all(night_route.photo_of(pl["order"][i]) for i in pl["lit"]))
        self.assertLess(pl["t_dim"], pl["t_draw"])
        self.assertLess(pl["t_draw"], pl["t_hold"])
        self.assertLess(pl["t_hold"], pl["t_end"])
        # offline: no map tiles, no Commons photos; the frames still draw (plain night field, lamps for every stop)
        with mock.patch("marketing.basemap.draw", side_effect=OSError("offline")), \
                mock.patch("marketing.night_route.fetch", side_effect=OSError("offline")), \
                mock.patch("marketing.night_route.time.sleep"):
            base, credit = night_route.backdrop(pl)
            top, meds, credits = night_route.overlay(pl)
        self.assertEqual((meds, credits, credit), ([], [], ""))
        for t in (0.0, pl["t_draw"] + 1.0, pl["t_hold"] + 0.5):
            self.assertEqual(night_route.frame(base, top, meds, pl, t).size, (night_route.W, night_route.H))
        self.assertEqual(night_route.end_frame(pl, 1.0, [("A. Photographer", "CC BY-SA 4.0")], "").size, (night_route.W, night_route.H))
        self.assertEqual(night_route.path_to(pl, 0)[1], pl["xy"][0])
        self.assertEqual(night_route.path_to(pl, len(pl["order"]))[1], pl["xy"][-1])
        self.assertEqual(night_route.camera(pl, 0.0), (0.0, 0.0, 1.0))  # the cover and the hold show the whole route
        self.assertEqual(night_route.camera(pl, pl["t_hold"] + 1.0), (0.0, 0.0, 1.0))
        self.assertAlmostEqual(night_route.camera(pl, (pl["t_draw"] + pl["t_hold"]) / 2)[2], night_route.ZOOM)
        # the voiceover: five lines from the guide, and beats that stretch to fit the recorded lines
        lines = night_route.script(pl)
        self.assertEqual(len(lines), 5)
        self.assertIn("17 pujos in one night", lines[0][0])  # English first for route posts (owner, 17 Oct)
        self.assertIn("Sovabazar Metro", lines[1][0])
        self.assertIn("Central Kolkata", lines[4][0])
        self.assertIn("১৭টা পুজো", lines[0][1])
        self.assertEqual(night_route.en_hours(3.5), "three and a half hours")
        self.assertEqual(night_route.en_hours(1.5), "an hour and a half")
        self.assertEqual(night_route.bn_hours(3.5), "সাড়ে তিন")
        self.assertEqual(night_route.bn_hours(2.5), "আড়াই")
        self.assertEqual(night_route.bn_of("সল্টলেক"), "সল্টলেকের")
        long = night_route.plan("north", vo=[3.0, 4.0, 12.0, 4.0, 6.0])
        cues = long["cues"]
        self.assertGreaterEqual(cues[1], cues[0] + 3.0)
        self.assertGreaterEqual(cues[2], cues[1] + 4.0)
        self.assertGreaterEqual(long["t_hold"], cues[2] + 12.0)
        self.assertGreaterEqual(long["t_end"], cues[3] + 4.0)
        self.assertGreaterEqual(long["end_secs"], 6.0)
        self.assertEqual(night_route.vo_files(None), [])

    def test_download_percent_encodes_bengali_file_names(self):
        from unittest import mock
        from marketing.footage import factory
        seen = []

        def fake(req, timeout=None):
            seen.append(req.full_url)
            raise OSError("stop")
        with mock.patch("urllib.request.urlopen", fake), tempfile.TemporaryDirectory() as d, self.assertRaises(OSError):
            factory.download("https://upload.wikimedia.org/wikipedia/commons/e/e1/দূর্গা_(2).jpg", Path(d) / "x.jpg")
        self.assertEqual(seen, ["https://upload.wikimedia.org/wikipedia/commons/e/e1/%E0%A6%A6%E0%A7%82%E0%A6%B0%E0%A7%8D%E0%A6%97%E0%A6%BE_(2).jpg"])
        seen.clear()
        with mock.patch("urllib.request.urlopen", fake), tempfile.TemporaryDirectory() as d, self.assertRaises(OSError):
            factory.download("https://x.org/a/%E0%A6%8F_b.jpg", Path(d) / "x.jpg")
        self.assertEqual(seen, ["https://x.org/a/%E0%A6%8F_b.jpg"])  # already encoded: left alone

    def test_posting_windows_cover_the_day_once(self):
        from marketing.publish_batch import in_window
        for at in ("08:00", "12:59", "13:00", "17:59", "18:00", "23:00"):
            self.assertEqual(sum(in_window(at, w) for w in ("am", "pm", "night")), 1, at)
        self.assertTrue(in_window("12:40", "am") and in_window("13:20", "pm") and in_window("22:40", "night"))

    def test_factory_rejects_tif_stills_in_reels(self):
        from marketing.footage import factory
        plan = {"date": "2026-10-01", "clips": {}, "items": [
            {"id": "r1", "type": "reel", "at": "10:00", "segments": [["x", 0, 3.0, ""]]}]}
        idx = {"x": {"url": "https://upload.wikimedia.org/a/b/Pandal.tif", "license": "CC BY 3.0", "artist": "a"}}
        with self.assertRaises(SystemExit) as e:
            factory.check(plan, idx)
        self.assertIn(".tif file", str(e.exception))
