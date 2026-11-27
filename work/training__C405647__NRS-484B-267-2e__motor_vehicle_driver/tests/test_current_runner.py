"""Current Native construction and distinct requested controls."""
import copy
import json
from pathlib import Path
import unittest

from runner import AID, check, requested_velocities


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())

    def test_exact_case_variants(self):
        for index in range(1, 6):
            with self.subTest(index=index):
                config = copy.deepcopy(self.config)
                config["case_id"] = f"{AID}__probe_0{index}"
                config["requested_response"] = "move_nonadjacent" if index == 1 else "stay_adjacent"
                config["requested_source_mode"] = "visible_hand_signal" if index == 4 else "moving_vehicle"
                self.assertFalse(check(config)["carla_contacted"])

    def test_move_over_window_and_other_controls(self):
        self.assertEqual(requested_velocities("01", 79)["ego"][1], 0)
        self.assertLess(requested_velocities("01", 80)["ego"][1], 0)
        self.assertLess(requested_velocities("01", 159)["ego"][1], 0)
        self.assertEqual(requested_velocities("01", 160)["ego"][1], 0)
        self.assertEqual(requested_velocities("02", 100)["ego"][1], 0)
        self.assertIsNotNone(requested_velocities("03", 100)["traffic"])
        self.assertEqual(requested_velocities("04", 100)["emergency"][0], 0)
        self.assertGreater(requested_velocities("05", 100)["emergency"][0], 0)
        self.assertFalse(requested_velocities("03", 100)["lane_change_safe_claimed"])

    def test_camera_and_duration_profile_rejected_when_changed(self):
        config = copy.deepcopy(self.config)
        config["cameras"][1]["name"] = "unreviewed"
        with self.assertRaisesRegex(ValueError, "Four-view"):
            check(config)
        config = copy.deepcopy(self.config)
        config["duration_s"] = 15
        with self.assertRaisesRegex(ValueError, "Full capture"):
            check(config)


if __name__ == "__main__":
    unittest.main()
