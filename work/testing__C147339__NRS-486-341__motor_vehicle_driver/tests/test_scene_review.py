"""Reviewed source-byte and classification gates before Native connection."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scene_review import SOURCE_KEYS, reviewed_scene
from test_lane_use import site as diagnostic_site

ROOT = Path(__file__).resolve().parents[1]


class SceneReviewTests(unittest.TestCase):
    def packet(self, root):
        sources = {}
        for key in SOURCE_KEYS:
            path = root / (key + ".txt")
            path.write_text("original reviewed " + key + "\n", encoding="utf-8")
            sources[key] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        site = diagnostic_site()
        bindings = {
            "map_source_sha256": "map", "lane_source_sha256": "lane_geometry",
            "highway_source_sha256": "highway",
            "public_maintenance_source_sha256": "public_maintenance",
            "public_vehicle_access_source_sha256": "public_vehicle_access",
            "ego_blueprint_source_sha256": "ego_blueprint",
            "motorcycle_class_source_sha256": "motorcycle_class",
            "moped_class_source_sha256": "moped_class",
            "motorcycle_exclusion_review_sha256": "motorcycle_exclusion_review",
        }
        for field, key in bindings.items():
            site[field] = sources[key]["sha256"]
        site["protected_route"]["source_sha256"] = sources["protected_route"]["sha256"]
        for name in ("adjacent", "edge", "deep"):
            site["ego_routes"][name]["source_sha256"] = sources["ego_route_" + name]["sha256"]
        case_id = ROOT.name + "__motorcycle_edge_encroach"
        packet = {"format": "c147339-reviewed-original-v1", "source_kind": "original_reviewed",
                  "diagnostic_fixture": False, "reviewer": "fixture reviewer", "case_id": case_id,
                  "map_id": "FixtureTown", "opendrive_sha256": "fixture-map-bytes",
                  "ego_blueprint_id": "vehicle.fixture.car", "protected_blueprint_id": "vehicle.fixture.bike",
                  "protected_vehicle_class": "motorcycle", "ego_vehicle_class": "motor_vehicle",
                  "sources": sources, "site": site}
        path = root / "scene.json"
        path.write_text(json.dumps(packet) + "\n", encoding="utf-8")
        return path, packet, case_id

    def test_source_bound_review_and_mutation_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, packet, case_id = self.packet(Path(tmp))
            self.assertEqual(reviewed_scene(path, case_id)["case_id"], case_id)
            (Path(tmp) / "lane_geometry.txt").write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source hash changed"):
                reviewed_scene(path, case_id)

    def test_fixture_and_class_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, packet, case_id = self.packet(Path(tmp))
            packet["diagnostic_fixture"] = True
            path.write_text(json.dumps(packet) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "original reviewed source required"):
                reviewed_scene(path, case_id)
            packet["diagnostic_fixture"] = False
            packet["protected_vehicle_class"] = "moped"
            path.write_text(json.dumps(packet) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "protected vehicle class differs"):
                reviewed_scene(path, case_id)


if __name__ == "__main__":
    unittest.main()
