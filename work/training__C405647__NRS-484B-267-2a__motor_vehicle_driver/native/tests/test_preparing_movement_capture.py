import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from preparing_movement_capture import check, check_config


class PreparingMovementCaptureTest(unittest.TestCase):
    def setUp(self):
        bundle = json.loads((ROOT / "preparing/visible_vehicle_movement/construction.json").read_text())
        self.config = json.loads(next(item["content"] for item in bundle["files"]
                                      if item["path"] == "config.json"))
        self.survey = {"source_kind": "original_native_site_survey",
                       "cell": {"layout": "road", "maneuver": "travel",
                                "control": "emergency_vehicle"},
                       "map_name": "Town03", "ego_blueprint": "vehicle.test.ego",
                       "emergency_blueprint": "vehicle.test.emergency",
                       "ego_spawn_xyz_yaw_deg": [0, 0, 0.5, 0],
                       "emergency_spawn_xyz_yaw_deg": [150, 0, 0.5, 0],
                       "emergency_authorization_source_id": "original:authorization",
                       "flashing_equipment_source_id": "original:equipment",
                       "flashing_qualification_source_id": "original:flashing-review",
                       "road_context_source_id": "original:road",
                       "weather_context_source_id": "original:weather",
                       "officer_direction_source_id": "original:officer",
                       "officer_direction": None,
                       "camera_poses": {name: [0, 0, 2, 0, 0, 0]
                                        for name in ("overview", "approach",
                                                     "reference_corner", "driver_reference")}}

    def test_exact_movement_config_and_survey(self):
        self.assertEqual(check_config(self.config)["frames"], 600)
        self.assertFalse(check(self.config, self.survey)["physical_completion_claimed"])

    def test_moving_previously_rejected(self):
        self.config["other_vehicle_start_frame"] = 0
        with self.assertRaisesRegex(ValueError, "movement intervention changed"):
            check_config(self.config)

    def test_survey_missing_original_qualification_rejected(self):
        self.survey.pop("flashing_qualification_source_id")
        with self.assertRaisesRegex(ValueError, "Original qualification"):
            check(self.config, self.survey)

    def test_hand_signal_case_cannot_use_movement_capture(self):
        self.config["case_id"] = self.config["case_id"].replace(
            "visible_vehicle_movement", "visible_driver_hand_signal")
        self.config["selected_case_id"] = self.config["case_id"]
        with self.assertRaisesRegex(ValueError, "Exact case identity"):
            check_config(self.config)


if __name__ == "__main__":
    unittest.main()
