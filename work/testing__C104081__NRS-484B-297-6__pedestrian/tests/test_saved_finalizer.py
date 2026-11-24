import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from delivery_audit import CAMERAS
from saved_finalizer import build_result, finalize
from saved_measurement import measure_saved
from test_saved_measurement import SavedMeasurementTests


class SavedFinalizerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = SavedMeasurementTests(methodName="test_blocked_intervening_lane_use_and_return")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.case_id = self.fixture.case_id

    def _audit(self):
        measured = measure_saved(self.root, self.case_id)
        return {
            "source_packet_sha256": measured["source_packet_sha256"],
            "measured_observables": measured["observables"],
            "original_frame_count": measured["sample_count"],
            "sealed_camera_media": {name: {"path": name + ".mkv"} for name in CAMERAS},
        }

    def test_canonical_result_records_sources_without_physical_claim(self):
        with patch("saved_finalizer.audit_saved", return_value=self._audit()):
            path = finalize(self.root, self.case_id, diagnostic=True, decode_media=False)
        result = json.loads(path.read_text())
        self.assertEqual(result["case_id"], self.case_id)
        self.assertTrue(result["diagnostic_fixture"])
        self.assertEqual(len(result["target_checks"]), 5)
        self.assertTrue(all(c["matched"] for c in result["target_checks"]))
        self.assertTrue(all(not c["physical_cause_confirmed"] for c in result["target_checks"]))
        self.assertFalse(result["maneuver_completed"])
        self.assertEqual(result["legal_judgment"], "unresolved")
        with patch("saved_finalizer.audit_saved", return_value=self._audit()):
            with self.assertRaisesRegex(ValueError, "Retain prior result"):
                finalize(self.root, self.case_id, diagnostic=True, decode_media=False)

    def test_audit_measurement_source_disagreement_rejected(self):
        audit = self._audit()
        audit["source_packet_sha256"] = "0" * 64
        with patch("saved_finalizer.audit_saved", return_value=audit):
            with self.assertRaisesRegex(ValueError, "source packet differ"):
                build_result(self.root, self.case_id, diagnostic=True)

    def test_missing_saved_source_rejected(self):
        (self.root / "traffic_history.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, "missing required saved source"):
            build_result(self.root, self.case_id, diagnostic=True)


if __name__ == "__main__":
    unittest.main()
