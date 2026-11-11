import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lane_comparison_audit import audit_comparison


PREFIX = "heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver__"
FIXED = {"map_id": "Town", "lane_geometry_sha256": "geometry",
         "marking_inventory_sha256": "markings", "ego_blueprint": "vehicle",
         "camera_plan_sha256": "cameras", "duration_s": 8, "fps": 20}


def packet(suffix, inside, passing=None):
    fixed = dict(FIXED, passing_participant_id=passing)
    return {"case_id": PREFIX + suffix, "source_sha256": "source",
            "measurement_sha256": "measurement", "fixed": fixed,
            "frames": [{"full_footprint_inside": inside}],
            "passing_motion_source_sha256": "motion" if passing else None,
            "measured_order_reversal": bool(passing)}


class ComparisonAuditTests(unittest.TestCase):
    def test_containment_and_passing_pairs(self):
        a = packet("within_marked_lane", True)
        b = packet("unexcused_boundary_crossing", False)
        c = packet("passing_boundary_crossing", False, passing=7)
        self.assertIsNone(audit_comparison("ordinary_lane_containment", a, b)["legal_verdict"])
        self.assertEqual(audit_comparison("passing_exception_context", b, c)["status"],
                         "software_evidence_complete")

    def test_rejects_missing_or_changed_evidence(self):
        a = packet("within_marked_lane", True)
        b = packet("unexcused_boundary_crossing", False)
        c = packet("passing_boundary_crossing", False, passing=7)
        for field, value, error in (("source_sha256", None, "hash missing"),
                                    ("frames", [], "frame evidence missing")):
            bad = copy.deepcopy(b)
            bad[field] = value
            with self.assertRaisesRegex(ValueError, error):
                audit_comparison("ordinary_lane_containment", a, bad)
        bad = copy.deepcopy(b)
        bad["fixed"]["camera_plan_sha256"] = "different"
        with self.assertRaisesRegex(ValueError, "Fixed conditions changed"):
            audit_comparison("ordinary_lane_containment", a, bad)
        bad = copy.deepcopy(c)
        bad["passing_motion_source_sha256"] = None
        with self.assertRaisesRegex(ValueError, "Passing motion source hash missing"):
            audit_comparison("passing_exception_context", b, bad)
        bad = copy.deepcopy(c)
        bad["measured_order_reversal"] = False
        with self.assertRaisesRegex(ValueError, "order reversal missing"):
            audit_comparison("passing_exception_context", b, bad)
        bad = copy.deepcopy(c)
        bad["case_id"] = PREFIX + "wrong_case"
        with self.assertRaisesRegex(ValueError, "case identity mismatch"):
            audit_comparison("passing_exception_context", b, bad)


if __name__ == "__main__":
    unittest.main()
