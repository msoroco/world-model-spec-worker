import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as Obj

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reversal_phase import HeadingReversalPhase


class Actor:
    def __init__(self):
        self.yaw = 0.0

    def get_transform(self):
        return Obj(rotation=Obj(yaw=self.yaw))


class HeadingReversalPhaseTests(unittest.TestCase):
    def test_observed_heading_marks_complete_interval(self):
        phase, actor = HeadingReversalPhase(), Actor()
        values = []
        for frame, yaw in enumerate([0, 1, 2, 45, 90, 164, 165, 179, 179], 10):
            actor.yaw = yaw
            values.append(phase(frame, actor))
        self.assertEqual(values, [False, False, True, True, True, True,
                                  True, False, False])

    def test_incomplete_reversal_stays_open_and_clock_gap_rejected(self):
        phase, actor = HeadingReversalPhase(), Actor()
        self.assertFalse(phase(1, actor))
        actor.yaw = -30
        self.assertTrue(phase(2, actor))
        actor.yaw = -80
        self.assertTrue(phase(3, actor))
        self.assertFalse(phase.finished)
        with self.assertRaisesRegex(ValueError, "consecutive"):
            phase(5, actor)

    def test_invalid_thresholds_rejected(self):
        with self.assertRaisesRegex(ValueError, "threshold"):
            HeadingReversalPhase(start_threshold_deg=170, finish_threshold_deg=165)


if __name__ == "__main__":
    unittest.main()
