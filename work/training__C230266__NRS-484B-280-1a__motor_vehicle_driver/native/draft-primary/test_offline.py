import copy
import json
import tempfile
import unittest
from pathlib import Path

from runner import check, control, read_survey


class DraftNativeContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path("config.json").read_text())

    def test_exact_window_and_sources(self):
        result = check(self.config)
        self.assertEqual((result["frames"], result["rate_hz"]), (600, 20))
        self.assertEqual(len(result["source_views"]), 4)
        self.assertFalse(result["carla_contacted"])
        self.assertFalse(result["physical_completion"])

    def test_wrong_identity_or_short_window_rejected(self):
        for key, value in (("law_id", "NRS-484B-280-1c"), ("frames", 599),
                           ("physical_completion", True), ("legal_verdict", "compliant")):
            bad = copy.deepcopy(self.config)
            bad[key] = value
            with self.assertRaises(ValueError):
                check(bad)

    def test_missing_camera_rejected(self):
        bad = copy.deepcopy(self.config)
        bad["cameras"].pop()
        with self.assertRaisesRegex(ValueError, "Four named"):
            check(bad)

    def test_source_and_control(self):
        with self.assertRaises(FileNotFoundError):
            read_survey("missing-original-road-survey.json")
        source = {"source_kind": "original_native_road_survey", "map_name": "Town01",
                  "road_boundary_source": "survey-1", "vehicle_spawn_index": 0,
                  "pedestrian_spawn_xyz_m": [0, 1, 0.5],
                  "pedestrian_path_end_xyz_m": [0, -1, 0.5],
                  "pedestrian_walk_speed_mps": 1.2,
                  "pedestrian_classification_source": "original walker blueprint",
                  "control_relationship_source": "original driver input",
                  "pedestrian_crosses_vehicle_path": True}
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            path = Path(temporary) / "road_survey.json"
            path.write_text(json.dumps(source))
            self.assertTrue(read_survey(path)["pedestrian_crosses_vehicle_path"])
            source.pop("pedestrian_crosses_vehicle_path")
            path.write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError, "Original road"):
                read_survey(path)
        self.assertEqual(control(25, 8)["phase"], "approach_request")
        self.assertEqual(control(10, 8)["phase"], "slow_request")
        with self.assertRaisesRegex(ValueError, "Measured"):
            control(float("nan"), 8)


if __name__ == "__main__":
    unittest.main()
