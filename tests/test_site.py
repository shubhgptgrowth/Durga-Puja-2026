"""site.json is the one place the public address lives; index.html's link preview must agree with it."""
import unittest

from scripts import site


class SiteTest(unittest.TestCase):
    def test_index_html_matches_site_json(self):
        site.check()

    def test_normalise(self):
        self.assertEqual(site.normalise("https://pujoparikrama.in"), "https://pujoparikrama.in/")
        self.assertEqual(site.normalise(" https://a.github.io/Repo "), "https://a.github.io/Repo/")
        with self.assertRaises(SystemExit):
            site.normalise("http://insecure.example/")

    def test_display(self):
        self.assertEqual(site.display("https://pujoparikrama.in/"), "pujoparikrama.in")
        self.assertEqual(site.display("https://a.github.io/Repo/"), "a.github.io/Repo")


if __name__ == "__main__":
    unittest.main()
