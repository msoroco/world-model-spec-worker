import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from audit_comparison_receipts import ASSIGNMENT
from comparison_delivery import measured_from_original


class OriginalComparisonBindingTest(unittest.TestCase):
    def setUp(self):
        scratch = Path(".runtime-work")
        scratch.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.processed = self.root / "processed"
        (self.processed / "analysis").mkdir(parents=True)
        self.report = {"format": "worker-analysis-report", "analysis_complete": True,
                       "case_id": ASSIGNMENT + "__one_cycle",
                       "physical_acceptance_claimed": False,
                       "legal_verdict_claimed": False,
                       "measurements": {"cycle_count": {"value": 1, "sources": {"trace": "abc"}}},
                       "measured_values": {"case_suffix": "one_cycle",
                                           "complete_device_cycles_before_entry": 1}}
        self.path = self.processed / "analysis/analysis-report.json"
        self.path.write_text(json.dumps(self.report))

    @patch("comparison_delivery.analyze_measurements")
    def test_matching_original_measurement_passes(self, analyze):
        analyze.return_value = self.report
        values = measured_from_original(self.root / "original", self.processed, "one_cycle")
        self.assertEqual(values["complete_device_cycles_before_entry"], 1)
        analyze.assert_called_once_with(self.root / "original")

    @patch("comparison_delivery.analyze_measurements")
    def test_forged_saved_measurement_rejects(self, analyze):
        analyze.return_value = self.report
        forged = dict(self.report)
        forged["measured_values"] = {"case_suffix": "one_cycle",
                                     "complete_device_cycles_before_entry": 2}
        self.path.write_text(json.dumps(forged))
        with self.assertRaisesRegex(ValueError, "differs from original sources"):
            measured_from_original(self.root / "original", self.processed, "one_cycle")


if __name__ == "__main__":
    unittest.main()
