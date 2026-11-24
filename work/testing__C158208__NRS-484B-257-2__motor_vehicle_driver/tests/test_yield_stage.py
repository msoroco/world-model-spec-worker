import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("yield_stage", ROOT / "yield_stage.py")
stage = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = stage
spec.loader.exec_module(stage)


class StageTests(unittest.TestCase):
    def test_exact_comparison_knobs_and_other_control_variant(self):
        cases = {kind: stage.primary(stage.PREFIX + kind) for kind in stage.KINDS}
        self.assertEqual(set(cases), set(stage.KINDS))
        self.assertEqual(cases["yield_other_inside"].other_start_xy_m,
                         cases["yield_other_obligated"].other_start_xy_m)
        self.assertTrue(cases["yield_other_obligated"].other_stop_sign)
        self.assertFalse(cases["yield_other_inside"].other_stop_sign)
        self.assertNotEqual(cases["yield_other_inside"].other_start_xy_m,
                            cases["yield_other_approaching"].other_start_xy_m)
        self.assertEqual(cases["yield_other_approaching"].target_other_speed(0), 0)
        self.assertEqual(cases["yield_other_approaching"].target_other_speed(80), 5)
        self.assertEqual(cases["yield_other_inside"].target_other_speed(149), 0)
        self.assertEqual(cases["yield_other_inside"].target_other_speed(150), 5)
        self.assertEqual(cases["yield_no_slow"].target_ego_speed(before_reference=True,
                                                                 other_body_clear=False), 8)
        self.assertEqual(cases["yield_other_inside"].target_ego_speed(before_reference=True,
                                                                      other_body_clear=False), 2)
        self.assertTrue(cases["officer_control_exception"].officer_control_source_required)

    def test_unknown_case_and_invalid_motion_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown exact"):
            stage.primary(stage.PREFIX + "invented")
        with self.assertRaisesRegex(ValueError, "release tick"):
            stage.Stage(stage.PREFIX + "yield_other_approaching", other_release_tick=-1)
        with self.assertRaisesRegex(ValueError, "lower reference"):
            stage.Stage(stage.PREFIX + "yield_other_inside", reference_speed_mps=9)


if __name__ == "__main__":
    unittest.main()
