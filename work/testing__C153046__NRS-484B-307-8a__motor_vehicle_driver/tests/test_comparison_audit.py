import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_audit import audit, audit_receiving_direction


class ComparisonAuditTest(unittest.TestCase):
    def setUp(self):
        self.left = {"case_id": "a", "legal_judgment": "unresolved", "physical_acceptance_claimed": False,
                     "original_frames": 600, "site_sha256": "site", "trace_sha256": "trace-a",
                     "stop_reference_kind": "marked_crosswalk", "extreme_left_lane_id": "left"}
        self.right = {**self.left, "case_id": "b", "trace_sha256": "trace-b"}

    def test_fixed_site_and_independent_histories(self):
        out = audit(self.left, self.right, "a", "b")
        self.assertFalse(out["requested_difference_physically_confirmed"])

    def test_reject_changed_site(self):
        self.right["site_sha256"] = "other"
        with self.assertRaisesRegex(ValueError, "site or stop"):
            audit(self.left, self.right, "a", "b")

    def test_reject_reused_trace(self):
        self.right["trace_sha256"] = "trace-a"
        with self.assertRaisesRegex(ValueError, "same original"):
            audit(self.left, self.right, "a", "b")

    def test_reject_missing_source_and_wrong_case(self):
        self.right["trace_sha256"] = ""
        with self.assertRaisesRegex(ValueError, "source binding"):
            audit(self.left, self.right, "a", "b")
        self.right["trace_sha256"] = "trace-b"
        with self.assertRaisesRegex(ValueError, "case or legal"):
            audit(self.left, self.right, "a", "c")

    def test_separately_reviewed_receiving_direction_pair(self):
        common = {"opendrive": "a" * 64, "official_signal": "b" * 64,
                  "stop_reference": "c" * 64}
        one = {**self.left, "receiving_direction": "one_way_left",
               "source_hashes": {**common, "one_way_routes": "d" * 64}}
        two = {**self.right, "receiving_direction": "two_way", "site_sha256": "other",
               "source_hashes": {**common, "two_way_routes": "e" * 64}}
        out = audit_receiving_direction(one, two, "a", "b")
        self.assertEqual(out["comparison_id"], "receiving_direction")
        self.assertFalse(out["requested_difference_physically_confirmed"])
        two["source_hashes"]["official_signal"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "fixed approach"):
            audit_receiving_direction(one, two, "a", "b")

    def test_receiving_direction_pair_rejects_relabelled_route(self):
        common = {"opendrive": "a" * 64, "official_signal": "b" * 64,
                  "stop_reference": "c" * 64}
        one = {**self.left, "receiving_direction": "one_way_left",
               "source_hashes": {**common, "one_way_routes": "d" * 64}}
        two = {**self.right, "receiving_direction": "two_way", "site_sha256": "other",
               "source_hashes": {**common, "one_way_routes": "e" * 64}}
        with self.assertRaisesRegex(ValueError, "source inventory"):
            audit_receiving_direction(one, two, "a", "b")
