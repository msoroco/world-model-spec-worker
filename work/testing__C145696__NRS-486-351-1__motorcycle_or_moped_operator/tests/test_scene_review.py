import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("scene_review", ROOT / "scene_review.py")
import sys
sys.path.insert(0, str(ROOT))
scene_review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scene_review)


class ReviewedSceneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=".runtime-work")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.parameters = {"left_motion": "stationary", "right_motion": "stationary",
                           "maneuver": "between", "vehicle_class": "motorcycle",
                           "operator_status": "civilian", "performance_of_duty": "not_applicable",
                           "target_speed_mps": 4}
        survey = {"lanes": {
            "left": {"road_id": 4, "lane_id": -1, "travel_direction": "east",
                     "adjacent_right_lane_id": -2, "lane_type": "Driving", "spawn_transform": "L"},
            "right": {"road_id": 4, "lane_id": -2, "travel_direction": "east",
                      "adjacent_left_lane_id": -1, "lane_type": "Driving", "spawn_transform": "R"}},
            "split_route": {"entry_lane_id": -1, "exit_lane_id": -2,
                            "verified_drivable": True, "measured_clear_width_m": 2.4,
                            "waypoints": [[0, 0], [10, 0]]},
            "left_lane_route": {"waypoints": [[0, 0], [10, 0]]},
            "ego_body_width_m": .8, "ego_spawn_transform": "E"}
        self.scene = {"format": "c145696-reviewed-original-v1", "source_kind": "original_reviewed",
                      "diagnostic_fixture": False, "case_id": "exact", "reviewer": "independent",
                      "map_id": "Town05", "opendrive_sha256": "map-digest",
                      "ego_blueprint_id": "vehicle.bh.crossbike", "left_blueprint_id": "vehicle.audi.a2",
                      "right_blueprint_id": "vehicle.audi.a2", "survey": survey,
                      "operator_status": "civilian", "performance_of_duty": "not_applicable",
                      "ego_vehicle_class": "motorcycle", "sources": {}}
        for key in scene_review.SOURCE_KEYS:
            content = (key + " independently reviewed").encode()
            (self.root / key).write_bytes(content)
            self.scene["sources"][key] = {"path": key, "sha256": hashlib.sha256(content).hexdigest()}
        self.scene["classification_source_sha256"] = self.scene["sources"]["moped_classification"]["sha256"]
        for key in ("operator_identity", "police_status", "performance_of_duty"):
            self.scene[key + "_source_sha256"] = self.scene["sources"][key]["sha256"]
        self.path = self.root / "scene.json"
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.scene) + "\n")

    def test_exact_reviewed_packet_passes(self):
        self.assertEqual(scene_review.reviewed_scene(self.path, "exact", self.parameters)["map_id"], "Town05")

    def test_fixture_packet_rejected(self):
        self.scene["diagnostic_fixture"] = True
        self.save()
        with self.assertRaisesRegex(ValueError, "original reviewed"):
            scene_review.reviewed_scene(self.path, "exact", self.parameters)

    def test_stale_operator_source_rejected(self):
        (self.root / "performance_of_duty").write_text("changed")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            scene_review.reviewed_scene(self.path, "exact", self.parameters)

    def test_duty_mismatch_rejected(self):
        self.scene["performance_of_duty"] = "on_duty"
        self.save()
        with self.assertRaisesRegex(ValueError, "performance of duty differs"):
            scene_review.reviewed_scene(self.path, "exact", self.parameters)


if __name__ == "__main__":
    unittest.main()
