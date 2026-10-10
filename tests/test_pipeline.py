import copy
import json
import tempfile
import unittest
from pathlib import Path

from pipeline import config
from pipeline.__main__ import run
from pipeline.enrich import crowd_index, enrich
from pipeline.fitness import kcal_for, steps_for
from pipeline.geo import haversine_m, order_route, path_length
from pipeline.ingest import ingest
from pipeline.plan import plan
from pipeline.validate import ValidationError, validate


class GeoTests(unittest.TestCase):
    def test_haversine_known_distance(self):
        # Esplanade → Kalighat metro is roughly 5.4 km in a straight line.
        d = haversine_m((22.5640, 88.3510), (22.5175, 88.3462))
        self.assertAlmostEqual(d, 5195, delta=300)

    def test_order_route_beats_input_order(self):
        start = (0.0, 0.0)
        stops = [(0.0, 0.03), (0.0, 0.01), (0.0, 0.04), (0.0, 0.02)]
        order = order_route(start, stops)
        self.assertEqual(sorted(order), [0, 1, 2, 3])
        self.assertEqual(order, [1, 3, 0, 2])
        self.assertLessEqual(path_length([start] + [stops[i] for i in order]),
                             path_length([start] + stops))

    def test_order_route_trivial(self):
        self.assertEqual(order_route((0, 0), []), [])
        self.assertEqual(order_route((0, 0), [(1, 1)]), [0])


class FitnessTests(unittest.TestCase):
    def test_steps_scale_with_height(self):
        self.assertGreater(steps_for(1000, 150), steps_for(1000, 185))
        self.assertAlmostEqual(steps_for(1000), 1000 / (1.65 * 0.415), delta=1)

    def test_kcal(self):
        self.assertEqual(kcal_for(60, 0, 65), round(3.0 * 65))
        self.assertGreater(kcal_for(60, 0, 65, brisk=True), kcal_for(60, 0, 65))
        self.assertGreater(kcal_for(30, 30), kcal_for(30, 0))


class CrowdTests(unittest.TestCase):
    def test_dawn_quieter_than_peak(self):
        self.assertLess(crowd_index(5, 1.1, 6), crowd_index(5, 1.1, 20))

    def test_bounded(self):
        for h in range(24):
            self.assertTrue(0 <= crowd_index(5, 1.1, h) <= 100)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.data = ingest()

    def test_raw_data_is_valid(self):
        validate(self.data)

    def test_rejects_unknown_zone(self):
        bad = copy.deepcopy(self.data)
        bad["pandals"][0]["zone"] = "atlantis"
        with self.assertRaises(ValidationError) as cm:
            validate(bad)
        self.assertTrue(any("unknown zone" in e for e in cm.exception.errors))

    def test_rejects_out_of_city(self):
        bad = copy.deepcopy(self.data)
        bad["food"][0]["lat"] = 28.6  # Delhi
        with self.assertRaises(ValidationError):
            validate(bad)

    def test_rejects_duplicate_ids(self):
        bad = copy.deepcopy(self.data)
        bad["pandals"].append(dict(bad["pandals"][0]))
        with self.assertRaises(ValidationError) as cm:
            validate(bad)
        self.assertTrue(any("duplicate id" in e for e in cm.exception.errors))

    def test_every_pandal_and_zone_has_bengali_name(self):
        warnings = validate(self.data)
        self.assertFalse([w for w in warnings if "name_bn" in w])

    def test_rejects_bad_slot(self):
        bad = copy.deepcopy(self.data)
        bad["pandals"][0]["best_slot"] = "brunch"
        with self.assertRaises(ValidationError):
            validate(bad)


class EnrichPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = plan(enrich(ingest()))
        cls.by_id = {p["id"]: p for p in cls.data["pandals"]}

    def test_every_pandal_has_metro(self):
        for p in self.data["pandals"]:
            self.assertIn("nearest_metro", p)
            # Curated pandals are all metro-reachable; OSM-discovered neighbourhood pujas can be further out.
            limit = 4000 if p.get("geo_source") in ("curated", "osm") else 7000
            self.assertLess(p["nearest_metro"]["distance_m"], limit, p["id"])

    def test_food_within_radius(self):
        for p in self.data["pandals"]:
            for f in p["food"]:
                self.assertLessEqual(f["distance_m"], 2000)
            if p.get("geo_source") in ("curated", "osm"):
                self.assertTrue(p["food"], f"{p['id']} has no food suggestion")

    def test_known_food_link(self):
        # Putiram and Paramount sit right on College Square.
        food_ids = {f["id"] for f in self.by_id["college_square"]["food"]}
        self.assertTrue({"putiram", "paramount"} <= food_ids)

    def test_zone_route_covers_all_pandals(self):
        for z in self.data["zones"]:
            self.assertEqual(sorted(z["route"]["order"]), sorted(z["pandal_ids"]))
            self.assertGreater(z["route"]["steps"], 0)

    def test_itineraries(self):
        self.assertEqual(len(self.data["itineraries"]), len(config.CURATED_ITINERARIES))
        allnighter = next(i for i in self.data["itineraries"] if i["id"] == "all_nighter")
        ids = [s["pandal"] for seg in allnighter["segments"] if seg["type"] == "walk" for s in seg["stops"]]
        self.assertTrue(all(self.by_id[i]["popularity"] == 5 for i in ids))
        self.assertTrue(any(seg["type"] == "ride" for seg in allnighter["segments"]))
        for it in self.data["itineraries"]:
            self.assertGreater(it["totals"]["steps"], 1000, it["id"])


class EndToEndTests(unittest.TestCase):
    def test_run_writes_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = run(out_dir=Path(tmp))
            on_disk = json.loads((Path(tmp) / "guide.json").read_text())
            self.assertEqual(on_disk["meta"]["version"], bundle["meta"]["version"])
            self.assertEqual(on_disk["meta"]["counts"]["pandals"], len(on_disk["pandals"]))
            geo = json.loads((Path(tmp) / "guide.geojson").read_text())
            self.assertEqual(geo["type"], "FeatureCollection")

    def test_version_is_deterministic(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            self.assertEqual(run(out_dir=Path(a))["meta"]["version"], run(out_dir=Path(b))["meta"]["version"])


if __name__ == "__main__":
    unittest.main()


class AuditApplyTests(unittest.TestCase):
    def row(self, **kw):
        base = {"kind": "pandals", "id": "x", "name": "Tridhara Sammilani", "distance_m": 300, "similarity": 1.0,
                "osm_class": "amenity:place_of_worship", "osm_name": "Tridhara Sammilani"}
        return {**base, **kw}

    def test_accepts_confident_match(self):
        from pipeline.audit_apply import accept
        self.assertTrue(accept(self.row())[0])

    def test_rejects_roads_neighbourhoods_and_far_branches(self):
        from pipeline.audit_apply import accept
        self.assertFalse(accept(self.row(osm_class="highway:residential"))[0])
        self.assertFalse(accept(self.row(osm_class="place:suburb"))[0])
        self.assertFalse(accept(self.row(distance_m=3840))[0])
        self.assertFalse(accept(self.row(kind="food", osm_class="tourism:hotel"))[0])

    def test_name_subset_rule(self):
        from pipeline.audit_apply import accept
        ok, _ = accept(self.row(kind="parking", name="Lake Mall (Rashbehari)", osm_name="Lake Mall", similarity=0.42, osm_class="shop:mall"))
        self.assertTrue(ok)
        self.assertFalse(accept(self.row(osm_name="Milan Pally", similarity=0.3))[0])

    def test_osm_pins_get_tighter_radius(self):
        data = plan(enrich(ingest()))
        tri = next(p for p in data["pandals"] if p["id"] == "tridhara")
        self.assertEqual(tri["geo_source"], "osm")
        self.assertEqual(tri["checkin_radius_m"], config.CHECKIN_RADIUS_OSM_M)


class AwardsPanjikaHelpTests(unittest.TestCase):
    def write(self, text):
        d = tempfile.mkdtemp()
        f = Path(d) / "x.toml"
        f.write_text(text, encoding="utf-8")
        return f

    AWARD = '[[award]]\nid = "apss"\nname = "Asian Paints Sharad Shamman"\nshort = "Sharad Shamman"\nurl = "https://x.in/"\n'

    def test_awards_file_is_valid_and_sourced(self):
        from pipeline.enrich import load_awards
        ids = {p["id"] for p in ingest(config.RAW_DIR)["pandals"]}
        winners, awards = load_awards(pandal_ids=ids)
        self.assertTrue(awards)
        for pid, ws in winners.items():
            self.assertIn(pid, ids)
            self.assertEqual(ws, sorted(ws, key=lambda w: -w["year"]))   # newest first, for the app's badge
            self.assertTrue(all(w["source"].startswith("https://") for w in ws))

    def test_awards_reject_unknown_pandal_and_missing_source(self):
        from pipeline.enrich import load_awards
        ok = self.AWARD + '[[winner]]\naward = "apss"\nyear = 2025\ncategory = "Best Puja"\npandal = "bagbazar"\nsource = "https://x.in/w"\n'
        self.assertIn("bagbazar", load_awards(self.write(ok), {"bagbazar"})[0])
        with self.assertRaises(ValueError):
            load_awards(self.write(ok), {"somewhere_else"})
        with self.assertRaises(ValueError):
            load_awards(self.write(ok.replace('source = "https://x.in/w"', 'source = "x.in"')), {"bagbazar"})
        with self.assertRaises(ValueError):
            load_awards(self.write(ok.replace('award = "apss"\nyear', 'award = "nope"\nyear')), {"bagbazar"})

    def test_panjika_times(self):
        from pipeline.enrich import load_panjika
        pj = load_panjika()
        self.assertEqual(pj["day"], "ashtami")
        self.assertGreaterEqual(len(pj["panjika"]), 2)   # both almanacs, since they disagree
        bad = self.write('day = "ashtami"\n[[panjika]]\nid = "g"\nsandhi_start = "8:13"\nsandhi_end = "07:25"\nsource = "https://x.in/"\n')
        with self.assertRaises(ValueError):
            load_panjika(bad)

    def test_help_near_picks_the_nearest_within_reach(self):
        from pipeline.enrich import help_near
        pt = (22.5726, 88.3639)
        places = {"toilets": [{"lat": 22.5730, "lng": 88.3640, "name": "Near"}, {"lat": 22.5800, "lng": 88.3700, "name": "Far"}],
                  "hospitals": [{"lat": 22.6200, "lng": 88.4000, "name": "Too far"}],
                  "police": [{"lat": 22.5740, "lng": 88.3650, "name:en": "Thana", "name": "থানা"}]}
        h = help_near(pt, places)
        self.assertEqual(h["toilets"]["name"], "Near")
        self.assertNotIn("hospitals", h)   # beyond 3 km
        self.assertEqual(h["police"]["name"], "Thana")
        self.assertLess(h["toilets"]["distance_m"], 100)

    def test_help_near_prefers_an_emergency_hospital_and_skips_specialists(self):
        from pipeline.enrich import help_near
        pt = (22.5726, 88.3639)
        hosp = [{"lat": 22.5730, "lng": 88.3640, "name": "North Maternity Home"},
                {"lat": 22.5735, "lng": 88.3641, "name": "City Eye Hospital"},
                {"lat": 22.5740, "lng": 88.3645, "name": "Para Nursing Home"},
                {"lat": 22.5800, "lng": 88.3700, "name": "Medical College Hospital", "emergency": "yes"}]
        self.assertEqual(help_near(pt, {"hospitals": hosp})["hospitals"]["name"], "Medical College Hospital")
        self.assertTrue(help_near(pt, {"hospitals": hosp})["hospitals"]["emergency"])
        self.assertEqual(help_near(pt, {"hospitals": hosp[:3]})["hospitals"]["name"], "Para Nursing Home")   # no ER in reach
