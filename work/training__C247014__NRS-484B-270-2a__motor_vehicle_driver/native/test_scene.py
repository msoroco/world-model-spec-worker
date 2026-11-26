"""Focused geometry and control-plan proof; no CARLA connection."""

import unittest
from scene import CASES, LEFT_CENTER_Y_M, RIGHT_CENTER_Y_M, check, target
from runner import CAMERAS, check as runner_check, steering_command


class SceneTest(unittest.TestCase):
    def test_four_case_geometry_and_order(self):
        proof = check()
        self.assertEqual(len(proof["case_suffixes"]), 4)
        self.assertGreater(proof["pass_first_frame"], 260)
        for frame in range(proof["pass_first_frame"], proof["pass_last_frame"] + 1):
            self.assertEqual(target("witness_1", frame).ego_y_m, LEFT_CENTER_Y_M)
            self.assertEqual(target("witness_2", frame).ego_y_m, RIGHT_CENTER_Y_M)

    def test_exception_blocker_is_source_to_capture(self):
        for suffix in CASES:
            row = target(suffix, 200)
            self.assertEqual(row.left_blocker_x_m is not None, suffix == "exception_1_2")
            self.assertEqual(row.left_blocker_y_m, LEFT_CENTER_Y_M if suffix == "exception_1_2" else None)

    def test_bad_case_or_frame_rejects(self):
        for suffix, frame in (("other", 0), ("witness_1", -1), ("witness_1", 600)):
            with self.assertRaises(ValueError):
                target(suffix, frame)

    def test_native_runner_check_is_lazy_and_exact(self):
        self.assertEqual(len(CAMERAS), 4)
        for suffix in CASES:
            proof = runner_check(suffix)
            self.assertEqual(proof["frames"], 600)
            self.assertFalse(proof["native_imported"])
        with self.assertRaises(ValueError):
            runner_check("wrong")

    def test_leftward_controller_sign_and_yaw_correction(self):
        self.assertLess(steering_command(3.5, 0), 0)
        self.assertGreater(steering_command(-3.5, 0), 0)
        self.assertGreater(steering_command(0, 5), 0)


if __name__ == "__main__":
    unittest.main()
