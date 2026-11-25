"""Independent delivery audit rejects a forged saved measurement."""
import unittest
from unittest.mock import patch

from delivery_audit import verify_original_measurements


class DeliveryMeasurementBindingTests(unittest.TestCase):
    @patch("analysis.analyze_measurements")
    def test_matching_original_report_passes(self, analyze):
        fresh = {"case_id": "exact", "measured_values": {"cycles": 2},
                 "measurements": {"cycles": {"sources": {"trace": "sha"}}}}
        analyze.return_value = fresh
        verify_original_measurements("original", "exact",
                                     {"measured_values": fresh["measured_values"]}, fresh)
        analyze.assert_called_once_with("original")

    @patch("analysis.analyze_measurements")
    def test_forged_result_or_report_rejects(self, analyze):
        fresh = {"case_id": "exact", "measured_values": {"cycles": 2},
                 "measurements": {"cycles": {"sources": {"trace": "sha"}}}}
        analyze.return_value = fresh
        with self.assertRaisesRegex(ValueError, "differ from original sources"):
            verify_original_measurements("original", "exact",
                                         {"measured_values": {"cycles": 3}}, fresh)
        with self.assertRaisesRegex(ValueError, "differ from original sources"):
            verify_original_measurements("original", "exact",
                                         {"measured_values": fresh["measured_values"]},
                                         {**fresh, "measurements": {"cycles": {"sources": {"trace": "forged"}}}})


if __name__ == "__main__":
    unittest.main()
