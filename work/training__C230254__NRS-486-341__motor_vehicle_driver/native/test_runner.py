import json
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from runner import check, subject_transform


HERE = Path(__file__).resolve().parent


class RunnerCheck(unittest.TestCase):
    def test_both_exact_case_configs(self):
        configs = [json.loads((HERE / ("config-" + setting + ".json")).read_text())
                   for setting in ("full_lane_available", "blocked_by_ego")]
        for config in configs:
            self.assertEqual(check(config)["frames"], 600)
        fixed = set(configs[0]) - {"case_id", "selected_case_id", "requested_setting",
                                  "subject_lateral_offset_m", "case"}
        self.assertTrue(all(configs[0][key] == configs[1][key] for key in fixed))
        self.assertNotEqual(configs[0]["subject_lateral_offset_m"],
                            configs[1]["subject_lateral_offset_m"])

    def test_spawn_offset_relative_to_protected_heading(self):
        carla = N(Location=lambda **values: N(**values),
                  Rotation=lambda **values: N(**values),
                  Transform=lambda location, rotation: N(location=location, rotation=rotation))
        pose = {"xyz_m": [10, 20, 0.5], "yaw_deg": 90}
        full = subject_transform(carla, pose, 4.2, 8)
        blocked = subject_transform(carla, pose, 2.5, 8)
        self.assertAlmostEqual(full.location.x, 5.8)
        self.assertAlmostEqual(blocked.location.x, 7.5)
        self.assertAlmostEqual(full.location.y, blocked.location.y)


if __name__ == "__main__":
    unittest.main()
