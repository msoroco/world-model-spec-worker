"""CPU topology checks for the exact shared center-lane distance cases."""

import importlib.util
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path


path = Path(__file__).resolve().parents[1] / "center_lane_site.py"
spec = importlib.util.spec_from_file_location("center_lane_site_3b", path)
site_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site_module)


def packet(kind="short_travel"):
    relationship = "onto_highway" if kind == "onto_highway_contrast" else "from_highway"
    return {
        "public_highway_confirmed": True,
        "highway_road_id": "H",
        "ego_id": "ego-1", "driver_id": "ego-1",
        "native_map_source": {"path": "map.json", "sha256": "a" * 64},
        "highway_review_source": {"path": "review.json", "sha256": "b" * 64},
        "lanes": [
            {"id": "C", "road_id": "H", "center_turn_lane": True,
             "exclusive_turn_use": True, "permitted_turn_directions": ["negative", "positive"],
             "polygon_xy_m": [[0, -2], [100, -2], [100, 2], [0, 2]]},
            {"id": "E", "road_id": "H", "highway_through": True,
             "centreline_xy_m": [[0, 4], [100, 4]]},
            {"id": "W", "road_id": "H", "highway_through": True,
             "centreline_xy_m": [[100, -4], [0, -4]]},
        ],
        "junction": {"id": "J", "kind": "street_intersection"},
        "route": {"center_lane_id": "C", "relationship": relationship,
                  "approach_road_id": "S" if relationship == "onto_highway" else "H",
                  "departure_road_id": "H" if relationship == "onto_highway" else "S",
                  "waypoints_xy_m": [[0, 0], [40, 0], [80, 0]]},
    }


class CenterLaneSiteTests(unittest.TestCase):
    def test_four_exact_route_relationships(self):
        for kind in ("short_travel", "boundary_travel", "long_travel", "onto_highway_contrast"):
            with self.subTest(kind=kind):
                self.assertEqual(site_module.inspect_site(packet(kind), kind)["center_lane_id"], "C")

    def test_rejects_wrong_turn_direction_or_lane_design(self):
        p = packet()
        p["route"]["relationship"] = "onto_highway"
        with self.assertRaisesRegex(ValueError, "relationship"):
            site_module.inspect_site(p, "short_travel")
        p = packet()
        p["lanes"][0]["permitted_turn_directions"] = ["positive"]
        with self.assertRaisesRegex(ValueError, "bidirectional"):
            site_module.inspect_site(p, "short_travel")
        p = packet()
        p["junction"]["kind"] = "alley"
        with self.assertRaisesRegex(ValueError, "street intersection"):
            site_module.inspect_site(p, "short_travel")

    def test_reviewed_map_and_highway_bytes_must_match(self):
        scratch = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ".runtime-work/c382162-2233b-tests"))
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            live = "original OpenDRIVE lane source"
            (root / "map.json").write_text(json.dumps({
                "opendrive_sha256": hashlib.sha256(live.encode()).hexdigest()}) + "\n")
            (root / "review.json").write_text(json.dumps({
                "public_highway_confirmed": True,
                "single_bidirectional_turn_only_center_lane": True,
                "highway_road_id": "H",
                "center_lane_polygon_xy_m": packet()["lanes"][0]["polygon_xy_m"]}) + "\n")
            p = packet()
            for name, key in (("map.json", "native_map_source"),
                              ("review.json", "highway_review_source")):
                p[key] = {"path": name, "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest()}
            self.assertEqual(site_module.verify_reviewed_site(root, p, "short_travel", live)["center_lane_id"], "C")
            p["lanes"][0]["polygon_xy_m"][0][0] = 1
            with self.assertRaisesRegex(ValueError, "polygon"):
                site_module.verify_reviewed_site(root, p, "short_travel", live)
            p = packet()
            for name, key in (("map.json", "native_map_source"),
                              ("review.json", "highway_review_source")):
                p[key] = {"path": name, "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest()}
            with self.assertRaisesRegex(ValueError, "OpenDRIVE"):
                site_module.verify_reviewed_site(root, p, "short_travel", live + " changed")
            (root / "review.json").write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                site_module.verify_reviewed_site(root, p, "short_travel", live)


if __name__ == "__main__":
    unittest.main()
