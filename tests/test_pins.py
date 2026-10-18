"""pipeline.pins: when a pin may move, and to where."""
import unittest

from pipeline.pins import decide, google_pick, photo_cluster

ZONE = {"lat": "22.52", "lng": "88.36"}
ROW = {"name": "Maddox Square Sarbojanin"}


class PinsTest(unittest.TestCase):
    def test_one_stray_photo_never_moves_a_pin(self):
        self.assertIsNone(photo_cluster([{"lat": 22.52, "lng": 88.36}]))
        self.assertEqual(decide({"photos": [{"lat": 22.52, "lng": 88.36}]})[2], "no evidence")

    def test_two_photos_together_make_a_cluster(self):
        pt, n = photo_cluster([{"lat": 22.5200, "lng": 88.3600}, {"lat": 22.5205, "lng": 88.3602}, {"lat": 22.60, "lng": 88.40}])
        self.assertEqual(n, 2)
        self.assertAlmostEqual(pt[0], 22.52025, places=4)

    def test_photos_and_park_that_disagree_are_left_for_a_person(self):
        ev = {"photos": [{"lat": 22.52, "lng": 88.36}, {"lat": 22.5201, "lng": 88.3601}],
              "landmark": {"name": "Maddox Square", "kind": "leisure:park", "lat": 22.53, "lng": 88.36}}
        pt, src, note = decide(ev)
        self.assertIsNone(pt)
        self.assertIn("disagree", note)

    def test_google_listing_must_match_the_name_and_be_near_the_area(self):
        near = {"place_id": "a", "name": "Maddox Square Durga Puja", "lat": 22.525, "lng": 88.362}
        wrong_name = {"place_id": "b", "name": "Ekdalia Evergreen", "lat": 22.521, "lng": 88.365}
        far = {"place_id": "c", "name": "Maddox Square Durga Puja", "lat": 22.70, "lng": 88.36}
        self.assertEqual(google_pick(ROW, [wrong_name, far, near], ZONE)["place_id"], "a")
        self.assertIsNone(google_pick(ROW, [wrong_name, far], ZONE))

    def test_google_wins_over_photos(self):
        g = {"place_id": "a", "name": "Maddox Square Durga Puja", "lat": 22.525, "lng": 88.362}
        self.assertEqual(decide({"photos": []}, g)[1], "google")


if __name__ == "__main__":
    unittest.main()
