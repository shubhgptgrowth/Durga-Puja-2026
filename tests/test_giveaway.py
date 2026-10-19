"""Giveaway draw (marketing/giveaway.py): who counts as an entry, and that the draw is reproducible."""
import datetime as dt
import unittest

from marketing import giveaway

IST = giveaway.IST
CLOSE = dt.datetime(2026, 10, 19, 17, 0, tzinfo=IST)


def c(user, text, hhmm="12:00"):
    h, m = map(int, hhmm.split(":"))
    t = dt.datetime(2026, 10, 19, h, m, tzinfo=IST).astimezone(dt.timezone.utc)
    return {"username": user, "text": text, "timestamp": t.strftime("%Y-%m-%dT%H:%M:%S+0000")}


class GiveawayTest(unittest.TestCase):
    def test_valid_entries(self):
        comments = [
            c("rina", "PUJO Behala @a @b @c"),                          # valid
            c("rina", "PUJO again @d @e @f", "12:05"),                  # second entry from the same person
            c("amit", "pujo @x @y"),                                    # only 2 tagged
            c("tuli", "Lovely! @a @b @c"),                              # no keyword
            c("sona", "PUJO @sona @p @q"),                              # tagging yourself doesn't count: 2 others
            c("pujoparikramaguide", "PUJO @a @b @c"),                   # our own account
            c("late", "PUJO @a @b @c", "17:01"),                        # after the close
            c("bijoy", "পুজো উত্তর কলকাতা @a.b @c_d @e.f."),            # Bengali keyword, handles with dots
        ]
        got = [w for w, _ in giveaway.entries(comments, "pujoparikramaguide", CLOSE)]
        self.assertEqual(got, ["rina", "bijoy"])

    def test_draw_is_reproducible_and_unique(self):
        names = [f"user{i}" for i in range(30)]
        s1, w1 = giveaway.draw(names, "123", CLOSE.isoformat(), 8)
        s2, w2 = giveaway.draw(list(reversed(names)), "123", CLOSE.isoformat(), 8)
        self.assertEqual((s1, w1), (s2, w2))
        self.assertEqual(len(set(w1)), 8)
        self.assertNotEqual(giveaway.draw(names, "124", CLOSE.isoformat(), 8)[1], w1)
        self.assertEqual(len(giveaway.draw(names[:3], "123", CLOSE.isoformat(), 8)[1]), 3)

    def test_bundles(self):
        spec = "dumdum=dum dum,kestopur;saltlake=salt lake,new town;ultadanga=ultadanga,chinar park;beleghata=beleghata"
        b = giveaway.parse_bundles(spec)
        self.assertEqual(giveaway.bundle_of("PUJO Dum Dum Park @a @b @c", b), "dumdum")
        self.assertEqual(giveaway.bundle_of("pujo chinar park or salt lake?", b), "ultadanga")   # the one named first
        self.assertIsNone(giveaway.bundle_of("PUJO @dumdum_fan @b @c", b))                     # handles don't count
        valid = [("a", "PUJO Dum Dum"), ("b", "PUJO Dum Dum"), ("c", "PUJO salt lake"), ("d", "PUJO"), ("e", "PUJO")]
        res = giveaway.draw_bundles(valid, b, "1", "close", 2)
        got = {name: w for name, _, w, _ in res}
        self.assertIn(got["dumdum"], {"a", "b"})
        self.assertEqual(got["saltlake"], "c")
        self.assertIn(got["ultadanga"], {"d", "e"})                     # nobody named it: drawn from the loose entries
        self.assertIn(got["beleghata"], {"d", "e"})
        winners = [w for w in got.values() if w]
        self.assertEqual(len(winners), len(set(winners)))                # nobody wins twice
        self.assertEqual(res, giveaway.draw_bundles(valid, b, "1", "close", 2))


if __name__ == "__main__":
    unittest.main()
