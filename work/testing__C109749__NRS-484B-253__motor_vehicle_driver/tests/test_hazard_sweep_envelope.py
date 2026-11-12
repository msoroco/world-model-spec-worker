"""Verify the engineering sweep distinguishes actions without legal labels."""
import importlib.util
from pathlib import Path
import unittest


FOLDER = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("hazard_sweep_envelope", FOLDER / "hazard_sweep_envelope.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HazardSweepEnvelopeTests(unittest.TestCase):
    def test_three_control_patterns_and_occupied_intersection(self):
        result = MODULE.evaluate(FOLDER)
        self.assertTrue(result["distinct_control_patterns"])
        self.assertTrue(result["occupied_intersection_yields"])
        self.assertFalse(result["native_feasibility_proven"])
        self.assertFalse(result["legal_hazard_cutoff_asserted"])
        row = next(r for r in result["rows"] if r["measured_ttc_s"] == 4.0)
        self.assertEqual(row["states_by_control_setpoint"],
                         {"3.0": "turn", "4.0": "turn", "5.0": "yield"})

    def test_requires_distinct_setpoint_responses(self):
        class ConstantPolicy:
            def __init__(self, **kwargs):
                pass

            def step(self, **kwargs):
                return {"state": "yield"}

        original = MODULE.load_policy
        MODULE.load_policy = lambda path: ConstantPolicy
        try:
            with self.assertRaisesRegex(ValueError, "do not separate"):
                MODULE.evaluate(FOLDER)
        finally:
            MODULE.load_policy = original

    def test_seen_hazard_requires_clearance_before_turn(self):
        policy_type = MODULE.load_policy(FOLDER / "hazard_sweep_policy.py")
        policy = policy_type(release_ttc_s=4.0, approach_speed_mps=3.0)
        fixed = dict(distance_to_hold_m=1.0, ego_speed_mps=0.0,
                     oncoming_closing_speed_mps=4.0,
                     oncoming_in_intersection=False, turn_complete=False)
        def step(distance, cleared):
            return policy.step(**fixed,
                               oncoming_distance_to_conflict_m=distance,
                               oncoming_cleared=cleared)["state"]
        self.assertEqual(step(8.0, False), "yield")
        self.assertEqual(step(24.0, False), "yield")
        self.assertEqual(step(24.0, True), "turn")


if __name__ == "__main__":
    unittest.main()
