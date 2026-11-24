import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runner", ROOT / "runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class NativeDraftTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config.json").read_text())

    def test_exact_unselected_plan(self):
        receipt = runner.check(self.config)
        self.assertEqual(receipt["frame_count"], 600)
        self.assertEqual(len(receipt["views"]), 4)
        self.assertFalse(receipt["selected"])
        self.assertIsNone(receipt["measured_speed_mph"])

    def test_park_cell_change_rejected(self):
        self.config["frozen_cell"]["maneuver"] = "drive"
        with self.assertRaisesRegex(ValueError, "frozen cell changed"):
            runner.check(self.config)

    def test_claimed_outcome_rejected(self):
        self.config["legal_verdict"] = "violation"
        with self.assertRaisesRegex(ValueError, "unproved outcome claimed"):
            runner.check(self.config)

    def test_missing_scope_rejected(self):
        import tempfile
        survey = {"source_kind": "original_native_curb_route_survey", "map_name": "Town",
                  "road_source_id": "road", "curb_source_id": "curb", "approach_scope_source_id": "",
                  "parking_scope_source_id": "parking", "cell_layout": "road", "cell_maneuver": "park",
                  "cell_control": "curb", "spawn_xyz_yaw_deg": [0, 0, 0, 0],
                  "curb_stop_xyz_m": [0, 0, 0], "approach_end_frame": 300,
                  "parking_end_frame": 450}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "survey.json"
            path.write_text(json.dumps(survey))
            with self.assertRaisesRegex(ValueError, "temporal scope sources missing"):
                runner.read_survey(path)


if __name__ == "__main__":
    unittest.main()
