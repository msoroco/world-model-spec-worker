import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stop_control import StopApproach


class StopControlTests(unittest.TestCase):
    def test_both_approaches_require_measured_near_line_zero_speed(self):
        for segment, start, brake, forward in (
                ([[-5,-2],[-5,2]], [-9.7,0], [-5.7,0], [1,0]),
                ([[-2,-5],[2,-5]], [0,-9.7], [0,-5.7], [0,1])):
            control = StopApproach(segment, hold_frames=2)
            self.assertFalse(control.step(start, 0, forward, False)["hold"])
            self.assertTrue(control.step(brake, 2, forward, True)["hold"])
            self.assertTrue(control.step(brake, 0, forward, True)["hold"])
            decision = control.step(brake, 0, forward, True)
            self.assertEqual(decision["phase"], "released")
            self.assertFalse(decision["hold"])
            self.assertEqual(decision["recorded_zero_speed_frames_near_reference"], 2)

    def test_early_stop_far_from_line_does_not_release(self):
        control = StopApproach([[-5,-2],[-5,2]])
        self.assertTrue(control.step([-7,0], 5, [1,0], True)["hold"])
        for _ in range(4):
            decision = control.step([-7,0], 0, [1,0], True)
        self.assertEqual(decision["phase"], "holding")
        self.assertEqual(decision["recorded_zero_speed_frames_near_reference"], 0)

    def test_release_permission_cannot_skip_stop(self):
        control = StopApproach([[-5,-2],[-5,2]])
        self.assertFalse(control.step([-9,0], 0, [1,0], True)["hold"])
        self.assertTrue(control.step([-5.7,0], 2, [1,0], True)["hold"])
        self.assertEqual(control.step([-5.7,0], 0, [1,0], False)["phase"], "holding")


if __name__ == "__main__":
    unittest.main()
