import importlib.util
import json
import sys
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from road_geometry import construction_routes, pedestrian_faces_approach, side_of_highway
from site_source import load_reviewed_site


class RoadGeometryTests(unittest.TestCase):
    def test_both_approaches_and_both_sides(self):
        for direction in ("east", "west"):
            for side in ("left", "right"):
                with self.subTest(direction=direction, side=side):
                    vehicle, pedestrian = construction_routes(direction, side)
                    self.assertTrue(pedestrian_faces_approach(vehicle, pedestrian))
                    traffic_side = side_of_highway(vehicle, pedestrian.start)
                    self.assertEqual(traffic_side, "traffic_right" if side == "left" else "traffic_left")
                    self.assertEqual(pedestrian.start[1], pedestrian.end[1])

    def test_missing_or_stale_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            packet_path = root / "original-site.json"
            with self.assertRaisesRegex(ValueError, "missing reviewed original"):
                load_reviewed_site(packet_path)
            source = root / "map.txt"
            source.write_text("reviewed map source", encoding="utf-8")
            binding = {"path": source.name, "sha256": sha256(source.read_bytes()).hexdigest()}
            packet = {key: binding for key in ("public_highway_source", "public_access_source", "highway_boundaries_source", "sidewalk_inventory_source", "subsection_6_review_source")}
            packet.update({"map_name": "original-map", "map_sha256": binding["sha256"], "walking_segment": [0, 20], "reviewer": "fixture-only", "reviewed_public_highway": True, "reviewed_sidewalk_absent": True, "reviewed_subsection_6_inapplicable": True})
            packet_path.write_text(json.dumps(packet), encoding="utf-8")
            self.assertEqual(load_reviewed_site(packet_path)["map_name"], "original-map")
            source.write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "stale original source"):
                load_reviewed_site(packet_path)


if __name__ == "__main__":
    unittest.main()
