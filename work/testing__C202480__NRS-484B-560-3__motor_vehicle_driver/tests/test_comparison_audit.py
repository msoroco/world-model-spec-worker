"""Exercise the five planned comparisons against six closed synthetic attempts."""

import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from comparison_audit import audit
from saved_measurement import finalize_attempt
from test_saved_measurement import SavedMeasurementTests


class ComparisonAuditTests(unittest.TestCase):
    def setUp(self):
        self.attempts = {}
        for index in range(6):
            fixture = SavedMeasurementTests()
            fixture.case_index = index
            fixture.setUp()
            self.addCleanup(fixture.doCleanups)
            finalize_attempt(fixture.attempt, fixture.attempt / "analysis-report.json")
            self.attempts[fixture.case_id] = fixture.attempt
        self.comparisons = json.loads((HERE / "case-plan.json").read_text())["comparisons"]

    def _audit(self, comparison):
        left, right = [self.attempts[case] for case in comparison["case_ids"]]
        return audit(comparison["comparison_id"], left, right)

    def test_all_five_contrasts_use_original_measurements(self):
        for comparison in self.comparisons:
            with self.subTest(comparison=comparison["comparison_id"]):
                result = self._audit(comparison)
                self.assertEqual(result["case_ids"], comparison["case_ids"])
                self.assertEqual(len(result["source_hashes"]), 2)
                self.assertTrue(result["measured_difference"])
                self.assertFalse(result["physical_acceptance_claimed"])
                self.assertEqual(result["legal_judgment"], "unresolved")

    def test_changed_saved_result_rejected(self):
        case = self.comparisons[0]["case_ids"][1]
        path = self.attempts[case] / "result.json"
        result = json.loads(path.read_text())
        result["realized_observables"]["two_queue_aligned_frame_count"] = 0
        path.write_text(json.dumps(result))
        with self.assertRaisesRegex(ValueError, "saved result differs"):
            self._audit(self.comparisons[0])

    def test_wrong_exact_pair_rejected(self):
        first, second = self.comparisons[0]["case_ids"]
        with self.assertRaisesRegex(ValueError, "site packet does not select exact case"):
            audit(self.comparisons[0]["comparison_id"],
                  self.attempts[second], self.attempts[first])


if __name__ == "__main__":
    unittest.main()
