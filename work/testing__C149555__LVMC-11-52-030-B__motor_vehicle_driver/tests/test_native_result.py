"""Canonical result is written only after sealed physical measurements pass."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from freight_contract import SourceError
from native_result import write_native_result


CASE = "testing__C149555__LVMC-11-52-030-B__motor_vehicle_driver__freight_loading"


class NativeResultTests(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work" / "c149555-native-result-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("overview", "approach", "reference_corner", "driver_reference", "raw"):
            (self.root / (name + ".mkv")).write_bytes(b"video")
        self.manifest = {"case_id": CASE,
                         "sources": {"native_result": {"path": "freight-native-source.json", "sha256": "packet"}},
                         "raw_sources": {"motion": {"path": "freight_motion.jsonl", "sha256": "motion"}}}
        self.measured = {"observed_action": "loading", "commercial_status_reviewed": True,
                         "stopped_inside_zone": True, "inside_posted_window": True,
                         "final_halt_duration_s": 12.0}

    def test_canonical_fields_from_observed_source(self):
        captured = {}
        def writer(attempt, result):
            captured.update(result)
            return Path(attempt) / "result.json"
        with patch("native_result.audit_source_bundle", return_value=self.measured), \
             patch("native_result.require_case_completion", return_value={"physical_completion": True}):
            path = write_native_result(self.root, self.manifest, writer=writer)
        self.assertEqual(path.name, "result.json")
        self.assertEqual(len(captured["target_checks"]), 4)
        self.assertTrue(all(check["matched"] for check in captured["target_checks"]))
        self.assertFalse(captured["physical_acceptance_claimed"])
        self.assertEqual(captured["legal_conclusion"], "unresolved")

    def test_missing_original_video_rejected(self):
        (self.root / "raw.mkv").unlink()
        with patch("native_result.audit_source_bundle", return_value=self.measured), \
             patch("native_result.require_case_completion", return_value={"physical_completion": True}):
            with self.assertRaises(SourceError):
                write_native_result(self.root, self.manifest, writer=lambda *args: None)


if __name__ == "__main__":
    unittest.main()
