"""Prospective Native controller targets retain both exact stop requests."""

import math
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from school_native_plan import SchoolController, check_pair, plan


class NativePlan(unittest.TestCase):
    def test_pair_and_phase(self):
        proof = check_pair()
        self.assertEqual(proof["frames"], 600)
        self.assertEqual(proof["hold_interval"], [120, 250])
        self.assertIsNone(proof["physical_completion"])
        self.assertNotEqual(plan("probe_1")[130]["target_center_x_m"],
                            plan("probe_2")[130]["target_center_x_m"])

    def test_release_not_source_claim(self):
        rows = plan("probe_1")
        self.assertEqual(sum(row["requested_signal_release"] for row in rows), 1)
        self.assertNotIn("observed_release", rows[250])
        self.assertTrue(all(row["phase"] == "hold_for_observed_release"
                            for row in rows[120:250]))

    def test_exact_frame_times(self):
        rows = plan("probe_2")
        self.assertEqual([row["frame"] for row in rows], list(range(600)))
        self.assertEqual(rows[-1]["time_s"], 599 / 20)
        self.assertTrue(all(math.isfinite(row["target_center_x_m"]) for row in rows))

    def test_unknown_case_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown exact"):
            plan("unknown")

    def test_release_requires_observed_prior_stop(self):
        control = SchoolController("probe_1")
        premature = control.step(100, -30, 4, True, "signal_stopped")
        self.assertNotEqual(premature["phase"], "released")
        hold = control.step(130, -55 / 3.280839895013123, 0, True, None)
        self.assertEqual(hold["phase"], "brake_or_hold")
        still_hold = control.step(260, -55 / 3.280839895013123, 0, False, None)
        self.assertEqual(still_hold["phase"], "hold_pending_original_release")
        release = control.step(270, -55 / 3.280839895013123, 0, False,
                               "signal_stopped")
        self.assertEqual(release["phase"], "released")


if __name__ == "__main__":
    unittest.main()
