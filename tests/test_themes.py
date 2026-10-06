"""2026 pandal themes: every row is sourced, and themes reach the bundle."""
import csv
import json
import unittest

from pipeline import config
from pipeline.enrich import THEMES, load_themes


class ThemesTest(unittest.TestCase):
    def test_rows_are_sourced(self):
        rows = list(csv.DictReader(open(THEMES, encoding="utf-8")))
        self.assertTrue(rows)
        ids = [r["pandal_id"] for r in rows]
        self.assertEqual(len(ids), len(set(ids)), "one theme per pandal")
        for r in rows:
            self.assertTrue(r["title"].strip(), r["pandal_id"])
            self.assertTrue(r["source"].startswith("https://"), r["pandal_id"])
            self.assertTrue(r["source_date"].startswith("2026"), f"{r['pandal_id']}: only 2026 reports")

    def test_themes_reach_the_bundle(self):
        themes = load_themes()
        bundle = json.load(open(config.OUT_DIR / "guide.json", encoding="utf-8"))
        listed = {p["id"]: p for p in bundle["pandals"]}
        for pid, th in themes.items():
            if pid in listed:
                self.assertEqual(listed[pid].get("theme_2026", {}).get("title"), th["title"], pid)


if __name__ == "__main__":
    unittest.main()
