"""scripts/reels_feed.py: which links become Pujo Reels, how they are tied to pandals, and what the app is given."""
import json
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import reels_feed as rf  # noqa: E402

GUIDE = json.loads((ROOT / "app/data/guide.json").read_text(encoding="utf-8"))


def ig(i, caption, permalink=None, kind="VIDEO", ts="2026-10-09T10:00:00+0000"):
    return {"id": str(i), "caption": caption, "media_type": kind, "permalink": permalink or f"https://www.instagram.com/reel/ABCDE{i}/",
            "timestamp": ts}


class ReelsFeedTest(unittest.TestCase):
    def test_only_embeddable_links(self):
        self.assertEqual(rf.source_of("https://www.instagram.com/reel/Cx12abc_D-/?igsh=x"), ("ig", "https://www.instagram.com/reel/Cx12abc_D-/"))
        self.assertEqual(rf.source_of("https://instagram.com/someone/p/Cx12abcD/"), ("ig", "https://www.instagram.com/p/Cx12abcD/"))
        self.assertEqual(rf.source_of("https://youtu.be/dQw4w9WgXcQ"), ("yt", "https://www.youtube.com/shorts/dQw4w9WgXcQ"))
        self.assertEqual(rf.source_of("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=3")[0], "yt")
        self.assertEqual(rf.source_of("https://www.facebook.com/watch/?v=123")[0], "fb")
        for bad in ("http://www.instagram.com/reel/Cx12abc/", "https://evil.example/reel/Cx12abc/", "javascript:alert(1)", "", None,
                    "https://www.instagram.com/pujoparikrama.guide/"):
            self.assertIsNone(rf.source_of(bad), bad)

    def test_pandal_from_caption(self):
        m = rf.pandal_matchers(GUIDE)
        self.assertEqual(rf.match_pandal("Bagbazar's sabeki protima at dawn", m), "bagbazar")
        # the longer, more specific name wins over a shared word
        self.assertEqual(rf.match_pandal("Kumartuli Park Sarbojanin 2026 theme reveal", m), "kumartuli_park")
        self.assertIsNone(rf.match_pandal("Shubho Mahalaya from all of us", m))

    def test_title_and_credit(self):
        cap = "Dhak at dawn, North Kolkata 🥁\n\nClip: @dhaki_dada, used with permission. #DurgaPuja2026 #Kolkata"
        self.assertEqual(rf.title_of("Dhak at dawn #DurgaPuja2026 #Kolkata"), "Dhak at dawn")
        self.assertEqual(rf.credit_of(cap), "@dhaki_dada")
        self.assertEqual(rf.credit_of("Our own route reel"), rf.OUR_HANDLE)
        self.assertLessEqual(len(rf.title_of("word " * 60)), 90)

    def test_build(self):
        items = [ig(1, "Bagbazar sabeki protima #DurgaPuja2026", ts="2026-10-08T10:00:00+0000"),
                 ig(2, "A photo, not a video", kind="IMAGE"),
                 ig(3, "Paid partnership with a sweet shop #ad", ts="2026-10-10T09:00:00+0000")]
        extra = [{"url": "https://www.youtube.com/shorts/dQw4w9WgXcQ", "title": "Dhak practice", "credit": "@dhaki", "added": "2026-10-09"},
                 {"url": "https://www.instagram.com/reel/ABCDE1/", "title": "duplicate of our own post", "added": "2026-10-01"},
                 {"url": "https://example.com/video.mp4", "title": "not embeddable"},
                 {"url": "https://www.instagram.com/reel/ZZZZZ9/", "title": "x", "pandal": "not_a_pandal", "added": "2026-10-02"}]
        feed = rf.build(items, extra, GUIDE)
        reels = feed["reels"]
        self.assertEqual([r["url"] for r in reels], ["https://www.instagram.com/reel/ABCDE3/", "https://www.youtube.com/shorts/dQw4w9WgXcQ",
                                                      "https://www.instagram.com/reel/ABCDE1/", "https://www.instagram.com/reel/ZZZZZ9/"])
        self.assertTrue(reels[0].get("sponsored"), "paid posts are labelled")
        self.assertEqual(reels[2]["pandal"], "bagbazar")
        self.assertIsNone(reels[3]["pandal"], "unknown pandal ids are dropped")
        self.assertTrue(all(set(r) >= {"id", "src", "url", "title", "credit", "pandal", "at", "thumb"} for r in reels))
        self.assertEqual(len({r["id"] for r in reels}), len(reels))

    def test_hand_added_list_parses(self):
        data = tomllib.loads(rf.EXTRA.read_text(encoding="utf-8"))
        for e in data.get("reel", []):
            self.assertIsNotNone(rf.source_of(e.get("url")), e)


if __name__ == "__main__":
    unittest.main()
