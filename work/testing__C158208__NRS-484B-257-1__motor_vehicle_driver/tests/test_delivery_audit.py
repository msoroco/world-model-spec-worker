import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from camera_sources import write_camera_sources
from delivery_audit import ASSIGNMENT, audit
from saved_finalizer import finalize
from test_camera_sources import fixture


class DeliveryAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.attempt = self.root / "attempt"
        frames = fixture(self.attempt)
        write_camera_sources(self.attempt, frames, diagnostic_fixture=True)
        self.report = self.root / "saved-report.json"
        finalize(self.attempt, self.report, diagnostic_fixture=True)
        self.case = ASSIGNMENT + "__nearest_view_response"

    def test_diagnostic_joins_all_original_sources_without_accepting_physical(self):
        result = audit(self.attempt, self.report, case_id=self.case,
                       diagnostic_fixture=True)
        self.assertEqual(result["original_frames"], 3)
        self.assertEqual(result["decoded_camera_images"], 12)
        self.assertEqual(result["status"], "diagnostic_fixture_only")
        self.assertFalse(result["physical_acceptance"])

    def test_missing_original_camera_and_stale_saved_measurement_rejected(self):
        (self.attempt / "nearest-view-overview-original-png.zip").unlink()
        with self.assertRaises(FileNotFoundError):
            audit(self.attempt, self.report, case_id=self.case,
                  diagnostic_fixture=True)

    def test_stale_saved_report_and_wrong_case_rejected(self):
        data = json.loads(self.report.read_text())
        data["measurement"]["sample_count"] = 2
        self.report.write_text(json.dumps(data) + "\n")
        with self.assertRaisesRegex(ValueError, "saved measurement differs"):
            audit(self.attempt, self.report, case_id=self.case,
                  diagnostic_fixture=True)
        with self.assertRaisesRegex(ValueError, "case outside"):
            audit(self.attempt, self.report, case_id="wrong", diagnostic_fixture=True)

    def test_production_refuses_synthetic_provenance(self):
        with self.assertRaisesRegex(ValueError, "original capture provenance"):
            audit(self.attempt, self.report, case_id=self.case,
                  reviewed_expected={}, diagnostic_fixture=False)


if __name__ == "__main__":
    unittest.main()
