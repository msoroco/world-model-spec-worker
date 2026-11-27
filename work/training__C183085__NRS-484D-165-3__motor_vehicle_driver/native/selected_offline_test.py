import copy
import json
import unittest
from pathlib import Path

from runner import check, survey_source


class ShoulderLampOffline(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path("config.json").read_text())

    def test_exact_case_and_window(self):
        out = check(self.config)
        self.assertEqual(out["case_id"], self.config["case_id"])
        self.assertEqual((out["frames"], out["rate_hz"]), (600, 20))
        self.assertFalse(out["physical_completion"])

    def test_changed_source_plan_rejected(self):
        for key, value in (("case_id", "wrong"), ("frames", 599),
                           ("lamp_command", "assume_displayed"),
                           ("optical_target_kind", "legal_verdict"),
                           ("physical_completion", {"complete": True})):
            changed = copy.deepcopy(self.config)
            changed[key] = value
            with self.assertRaises(ValueError):
                check(changed)

    def test_camera_loss_rejected(self):
        changed = copy.deepcopy(self.config)
        changed["cameras"].pop()
        with self.assertRaisesRegex(ValueError, "Four cameras"):
            check(changed)

    def test_original_survey_required(self):
        from tempfile import TemporaryDirectory
        survey = {"source_kind": "original_native_shoulder_lighting_survey",
                  "map_name": "surveyed-map", "highway_identity_source": "map survey",
                  "adjacent_paved_shoulder_source": "map survey",
                  "passing_lane_source": "lane survey", "passing_traffic_side": "left",
                  "lighting_hours_source": "civil lighting section",
                  "civil_time_source": "original clock", "ambient_reveal_protocol_source": "optical survey",
                  "front_lamp_protocol_source": "optical survey",
                  "rear_lamp_protocol_source": "optical survey",
                  "shoulder_xyz_m": [0, 0, 0], "shoulder_yaw_deg": 0,
                  "passing_vehicle_spawn_index": 0,
                  "optical_target_kind": self.config["optical_target_kind"],
                  "target_distance_ft": self.config["target_distance_ft"]}
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "survey.json"
            path.write_text(json.dumps(survey))
            self.assertEqual(survey_source(path, self.config)["map_name"], "surveyed-map")
            for key in ("adjacent_paved_shoulder_source", "lighting_hours_source",
                        "front_lamp_protocol_source", "passing_lane_source"):
                changed = copy.deepcopy(survey)
                del changed[key]
                path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    survey_source(path, self.config)


if __name__ == "__main__":
    unittest.main()
