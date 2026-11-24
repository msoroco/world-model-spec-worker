import copy
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import audit
from saved_left_turn import ASSIGNMENT_ID

PLAN = ROOT / "case-plan.json"


def measured(suffix, source):
    row = {"frame": 100, "time_s": 5.0,
           "ego": {"full_body_inside": True},
           "opponent": {"full_body_inside": True},
           "heading_cosine": -1.0, "ego_speed_mps": 1.0,
           "opponent_speed_mps": 5.0, "ego_signal_left": True,
           "ego_turn_committed": False, "opponent_cleared": False,
           "ego_braking": True}
    return {"case_id": ASSIGNMENT_ID + "__" + suffix, "source_id": source,
            "map_sha256": "a" * 64, "physical_acceptance": "unverified",
            "frames": [row]}


class ComparisonAudit(unittest.TestCase):
    def test_initial_pair_checks_changed_ego_and_fixed_opponent(self):
        a, b = measured("inside_yield", "a"), measured("inside_no_yield", "b")
        b["frames"][0]["ego_braking"] = False
        self.assertEqual(audit(plan_path=PLAN, comparison_id="initial_within_yield", left=a, right=b)["checked_frames"], 1)
        b["frames"][0]["opponent_speed_mps"] = 7.0
        with self.assertRaisesRegex(ValueError, "fixed opponent"):
            audit(plan_path=PLAN, comparison_id="initial_within_yield", left=a, right=b)

    def test_rejects_case_reorder_and_source_reuse(self):
        a, b = measured("inside_yield", "a"), measured("inside_no_yield", "b")
        b["frames"][0]["ego_braking"] = False
        with self.assertRaisesRegex(ValueError, "case order"):
            audit(plan_path=PLAN, comparison_id="initial_within_yield", left=b, right=a)
        b["source_id"] = "a"
        with self.assertRaisesRegex(ValueError, "distinct original sources"):
            audit(plan_path=PLAN, comparison_id="initial_within_yield", left=a, right=b)

    def test_signal_pair_holds_turn_fixed(self):
        a, b = measured("signal_given", "a"), measured("signal_omitted", "b")
        b["frames"][0]["ego_signal_left"] = False
        self.assertEqual(audit(plan_path=PLAN, comparison_id="signal_condition", left=a, right=b)["declared_measured_difference"], ["ego_signal_left"])
        b["frames"][0]["ego_speed_mps"] = 2.0
        with self.assertRaisesRegex(ValueError, "fixed ego turn"):
            audit(plan_path=PLAN, comparison_id="signal_condition", left=a, right=b)

    def test_reciprocal_pair_needs_signal_and_later_difference(self):
        a, b = measured("reciprocal_yield", "a"), measured("reciprocal_no_yield", "b")
        b["frames"][0]["opponent_cleared"] = True
        self.assertEqual(audit(plan_path=PLAN, comparison_id="reciprocal_duty", left=a, right=b)["checked_frames"], 1)
        a["frames"][0]["ego_signal_left"] = False
        with self.assertRaisesRegex(ValueError, "observed left signal"):
            audit(plan_path=PLAN, comparison_id="reciprocal_duty", left=a, right=b)

    def test_rejects_frame_join_and_absent_difference(self):
        a, b = measured("inside_yield", "a"), measured("inside_no_yield", "b")
        with self.assertRaisesRegex(ValueError, "difference absent"):
            audit(plan_path=PLAN, comparison_id="initial_within_yield", left=a, right=b)
        b = copy.deepcopy(b)
        b["frames"][0]["ego_braking"] = False
        b["frames"][0]["time_s"] = 5.05
        with self.assertRaisesRegex(ValueError, "frame/time"):
            audit(plan_path=PLAN, comparison_id="initial_within_yield", left=a, right=b)


if __name__ == "__main__":
    unittest.main()
