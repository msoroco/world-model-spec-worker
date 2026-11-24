import math
import json
import tempfile
import unittest
from pathlib import Path

from reverse_alternative_route import ReverseRouteController, review_route
from reverse_alternative_capture import (ASSIGNMENT, CASES, _load_site,
                                         _publish_site_sources, capture)


BODY = [[15, -1], [17, -1], [17, 1], [15, 1]]


class ReverseAlternativeRouteTests(unittest.TestCase):
    def test_exact_site_sources_bind_both_routes(self):
        root = Path(__file__).resolve().parents[1]
        for suffix, alternative in (("reverse_into_intersection", "intersection"),
                                    ("reverse_around_street_corner", "street_corner")):
            site, review = _load_site(root, ASSIGNMENT + "__" + suffix)
            self.assertEqual(site["alternative"], alternative)
            self.assertEqual(CASES[ASSIGNMENT + "__" + suffix], (alternative, True))
            self.assertFalse(review["actual_motion_confirmed"])
        for suffix in ("reverse_stops_before_intersection",
                       "reverse_stops_before_street_corner"):
            site, review = _load_site(root, ASSIGNMENT + "__" + suffix)
            self.assertFalse(site["expected_entry"])
            self.assertEqual(max(review["planned_body_region_overlap_area_m2"]), 0)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            site = json.loads((root / "intersection_site.json").read_text())
            (target / "intersection_site.json").write_text(json.dumps(site))
            (target / site["geometry_source"]["path"]).write_text("changed\n")
            (target / site["camera_source"]["path"]).write_bytes(
                (root / site["camera_source"]["path"]).read_bytes())
            with self.assertRaisesRegex(ValueError, "Changed original site source"):
                _load_site(target, ASSIGNMENT + "__reverse_into_intersection")

    def test_intersection_body_enters_with_straight_backing(self):
        route = [[16 - i, 0] for i in range(11)]
        region = [[8, -3], [12, -3], [12, 3], [8, 3]]
        review = review_route(route, BODY, region, alternative="intersection")
        self.assertEqual(review["planned_heading_change_deg"], 0)
        self.assertGreater(max(review["planned_body_region_overlap_area_m2"]), 0)
        self.assertFalse(review["actual_motion_confirmed"])
        self.assertEqual(ReverseRouteController(route).step([16, 0], 0, 0)["steer"], 0)

    def test_corner_has_continuous_reverse_turn_and_steering(self):
        route = [[16 - i, 0] for i in range(9)]
        route += [[8 - 8 * math.sin(i * math.pi / 24),
                   -8 + 8 * math.cos(i * math.pi / 24)] for i in range(1, 13)]
        region = [[-2, -10], [11, -10], [11, 2], [-2, 2]]
        review = review_route(route, BODY, region, alternative="street_corner")
        self.assertGreater(abs(review["planned_heading_change_deg"]), 30)
        self.assertGreater(max(review["planned_body_region_overlap_area_m2"]), 0)
        command = ReverseRouteController(route).step([8, 0], 0, 1)
        self.assertTrue(command["reverse"])
        self.assertNotEqual(command["steer"], 0)

    def test_rejects_start_overlap_and_unconstructed_turn(self):
        route = [[16 - i, 0] for i in range(11)]
        with self.assertRaisesRegex(ValueError, "start body"):
            review_route(route, BODY, [[15, -2], [18, -2], [18, 2], [15, 2]],
                         alternative="intersection")
        with self.assertRaisesRegex(ValueError, "lacks a planned turn"):
            review_route(route, BODY, [[8, -3], [12, -3], [12, 3], [8, 3]],
                         alternative="street_corner")

    def test_stop_before_routes_keep_complete_body_clear(self):
        route = [[16, 0], [15, 0], [14, 0]]
        for alternative, region in (
            ("intersection", [[8, -3], [12, -3], [12, 3], [8, 3]]),
            ("street_corner", [[-2, -10], [11, -10], [11, 2], [-2, 2]])):
            review = review_route(route, BODY, region, alternative=alternative,
                                  expected_entry=False)
            self.assertEqual(max(review["planned_body_region_overlap_area_m2"]), 0)
            self.assertFalse(review["expected_entry"])

    def test_native_capture_rejects_synthetic_site_before_carla_import(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            site = json.loads((root / "intersection_site.json").read_text())
            (target / "construction.json").write_text("{}\n")
            (target / "intersection_site.json").write_text(json.dumps(site) + "\n")
            for source in ("geometry_source", "camera_source"):
                name = site[source]["path"]
                (target / name).write_bytes((root / name).read_bytes())
            with self.assertRaisesRegex(ValueError,
                                        "Original Native site and camera review required"):
                capture(target, "127.0.0.1", 2000,
                        ASSIGNMENT + "__reverse_into_intersection")

    def test_reviewed_template_publication_keeps_original_bytes(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            templates = target / "site_templates"
            templates.mkdir()
            case = ASSIGNMENT + "__reverse_into_intersection"
            site = json.loads((root / "intersection_site.json").read_text())
            for name in ("intersection_site.json", site["geometry_source"]["path"],
                         site["camera_source"]["path"]):
                (templates / name).write_bytes((root / name).read_bytes())
            loaded, _ = _load_site(target, case)
            self.assertEqual(loaded, site)
            _publish_site_sources(target, site, case)
            for name in ("intersection_site.json", site["geometry_source"]["path"],
                         site["camera_source"]["path"]):
                self.assertEqual((target / name).read_bytes(),
                                 (templates / name).read_bytes())
            (target / "intersection_site.json").write_text("changed\n")
            with self.assertRaisesRegex(ValueError, "differs from reviewed template"):
                _publish_site_sources(target, site, case)


if __name__ == "__main__":
    unittest.main()
