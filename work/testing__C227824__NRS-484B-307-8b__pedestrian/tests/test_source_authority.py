import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from source_authority import verify


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        private = ROOT.parents[1] / ".runtime-work"
        private.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=private)
        self.root = Path(self.temp.name)
        self.scene = {
            "route_id": "source-test-route", "highway_polygon_xy_m": [[0, 0], [2, 0], [2, 2], [0, 2]],
            "governing_pedestrian_device_ids": [8],
            "camera_placements": {"overview": {"location_xyz_m": [0, 0, 3],
                                                "target_xyz_m": [1, 1, 1]}},
            "production_source_review": {
                "complete": True, "route_id": "source-test-route",
                "facing_signal_source_id": "head-1", "controller_source_id": "controller-1",
            },
        }
        self.put("candidate-corridor.xodr", '<OpenDRIVE><road><signals><signal id="head-1"/></signals></road><controller id="controller-1"><control signalId="head-1"/></controller></OpenDRIVE>\n')
        self.scene["map_source_sha256"] = self.digest("candidate-corridor.xodr")
        for name, review_key, source_key, value in (
            ("inventory-review.json", "device_inventory_review", "device_ids", [8]),
            ("camera-review.json", "camera_placement_review", "camera_placements",
             self.scene["camera_placements"]),
        ):
            self.put(name, json.dumps({"route_id": "source-test-route",
                                       "source_evidence": "synthetic unit test only",
                                       source_key: value}) + "\n")
            self.scene[review_key] = {"complete": True, "source_path": name,
                                      "source_sha256": self.digest(name)}
        for name, extra in (
            ("official_signal", {"signal_source_id": "head-1"}),
            ("pedestrian_device_driver", {"governing_device_ids": [8],
                                           "readback_api": "set_pedestrian_indication,get_state,get_countdown"}),
            ("highway_boundary_survey", {"polygon_xy_m": self.scene["highway_polygon_xy_m"]}),
        ):
            path = name + ".json"
            self.put(path, json.dumps({"route_id": "source-test-route",
                                       "source_evidence": "test-only declaration", **extra}) + "\n")
            self.scene["production_source_review"][name] = {"path": path, "sha256": self.digest(path)}

    def tearDown(self):
        self.temp.cleanup()

    def put(self, name, content):
        (self.root / name).write_text(content)

    def digest(self, name):
        return hashlib.sha256((self.root / name).read_bytes()).hexdigest()

    def test_source_bound_synthetic_review(self):
        result = verify(self.scene, self.root)
        self.assertTrue(result["source_reviewed"])
        self.assertFalse(result["physical_acceptance_claimed"])

    def test_reject_diagnostic_and_missing_map_controller(self):
        self.scene["diagnostic_fixture"] = True
        with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
            verify(self.scene, self.root)
        self.scene.pop("diagnostic_fixture")
        self.put("candidate-corridor.xodr", "<OpenDRIVE/>\n")
        self.scene["map_source_sha256"] = self.digest("candidate-corridor.xodr")
        with self.assertRaisesRegex(ValueError, "signal/controller"):
            verify(self.scene, self.root)

    def test_reject_stale_driver_and_boundary(self):
        self.put("pedestrian_device_driver.json", "{}\n")
        with self.assertRaisesRegex(ValueError, "source hash differs"):
            verify(self.scene, self.root)
        self.scene["production_source_review"]["pedestrian_device_driver"]["sha256"] = self.digest("pedestrian_device_driver.json")
        with self.assertRaisesRegex(ValueError, "route identity differs"):
            verify(self.scene, self.root)
        self.scene["production_source_review"]["pedestrian_device_driver"] = {
            "path": "highway_boundary_survey.json", "sha256": self.digest("highway_boundary_survey.json")}
        with self.assertRaisesRegex(ValueError, "device inventory differs"):
            verify(self.scene, self.root)

    def test_reject_controller_for_another_head(self):
        self.put("candidate-corridor.xodr", '<OpenDRIVE><road><signals><signal id="head-1"/><signal id="head-2"/></signals></road><controller id="controller-1"><control signalId="head-2"/></controller></OpenDRIVE>\n')
        self.scene["map_source_sha256"] = self.digest("candidate-corridor.xodr")
        with self.assertRaisesRegex(ValueError, "does not govern facing signal"):
            verify(self.scene, self.root)

    def test_reject_inventory_and_camera_review_drift(self):
        self.scene["governing_pedestrian_device_ids"] = []
        with self.assertRaisesRegex(ValueError, "governing-device inventory review differs"):
            verify(self.scene, self.root)
        self.scene["governing_pedestrian_device_ids"] = [8]
        self.scene["camera_placements"]["overview"]["target_xyz_m"] = [2, 2, 1]
        with self.assertRaisesRegex(ValueError, "camera placement review differs"):
            verify(self.scene, self.root)


if __name__ == "__main__":
    unittest.main()
