"""CPU tests for exact comparison isolation and source identity gates."""

import unittest

from comparison_audit import audit, definitions


def receipts(pair):
    return [{"format": "c380107-original-delivery-audit-v1", "case_id": case_id,
             "source_kind": "original_native_attempt", "frames_checked": 900,
             "physical_completion": "requires independent local review",
             "attempt_id": "attempt-%d" % i, "trace_sha256": "trace-%d" % i,
             "site_sha256": "same-site", "measurement": {
                 "rear_gap_crossing_frame": 200, "posted_limit_mps": 9.0,
                 "extreme_left_lane_id": "L0", "hov_designation_state": "unresolved",
                 "hov_compliance_state": "unresolved"}}
            for i, case_id in enumerate(pair["case_ids"])]


class ComparisonAuditTests(unittest.TestCase):
    def test_all_eleven_selected_isolations(self):
        _, comparisons = definitions()
        self.assertEqual(len(comparisons), 11)
        for name, pair in comparisons.items():
            with self.subTest(name=name):
                result = audit(name, *receipts(pair))
                self.assertFalse(result["physical_acceptance"])

    def test_changed_site_refused(self):
        _, comparisons = definitions()
        pair = comparisons["core_vs_qualified_hov"]
        rows = receipts(pair)
        rows[1]["site_sha256"] = "changed"
        with self.assertRaisesRegex(ValueError, "site changed"):
            audit(pair["comparison_id"], *rows)

    def test_duplicate_motion_refused(self):
        _, comparisons = definitions()
        pair = comparisons["core_vs_qualified_hov"]
        rows = receipts(pair)
        rows[1]["trace_sha256"] = rows[0]["trace_sha256"]
        with self.assertRaisesRegex(ValueError, "reuses"):
            audit(pair["comparison_id"], *rows)


if __name__ == "__main__":
    unittest.main()
