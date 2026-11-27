"""Canonical saved-only result and missing-original-source checks."""

import json
from pathlib import Path
import tempfile
import unittest

from finalize import finalize
from test_measure_uturn import fixture


class FinalizeSavedTest(unittest.TestCase):
    def setUp(self):
        root = Path.cwd() / ".runtime-work"
        root.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=root)
        self.folder = Path(self.tmp.name)
        fixture(self.folder, "authorized_opening")
        request = json.loads((self.folder / "request.json").read_text())
        case = request["case_id"]
        (self.folder / "config.json").write_text(json.dumps({"case_id": case,
            "selected_case_id": case}) + "\n")
        (self.folder / "construction.json").write_text(json.dumps({
            "case_id": case, "recording_description": "Synthetic U-turn source join"}) + "\n")
        (self.folder / "trace.jsonl").write_text('{"time_s":0}\n')
        (self.folder / "body_history.jsonl").write_text('{"frame":0}\n')
        (self.folder / "capture").mkdir()
        (self.folder / "capture/evidence.jsonl").write_text('{"frame":0}\n')
        for name in ("overview", "approach", "median_reference", "driver_reference"):
            (self.folder / (name + ".mkv")).write_bytes(b"synthetic-video-placeholder")

    def tearDown(self):
        self.tmp.cleanup()

    def test_saved_measurement_remains_unjudged_and_hash_bound(self):
        report = finalize(self.folder, self.folder / "analysis-report.json")
        result = json.loads((self.folder / "result.json").read_text())
        self.assertEqual(result["case_id"], report["case_id"])
        self.assertFalse(result["accepted"])
        self.assertFalse(result["maneuver_completed"])
        self.assertFalse(result["target_checks"][0]["physical_cause_confirmed"])
        self.assertFalse(report["physical_or_legal_acceptance"])
        self.assertEqual(len(result["recording_evidence"]), 2)
        self.assertEqual(len(report["measurements"]["opening_geometry"]["sources"]), 5)

    def test_missing_saved_body_source_rejected_before_result(self):
        (self.folder / "native-uturn.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required original source"):
            finalize(self.folder, self.folder / "analysis-report.json")
        self.assertFalse((self.folder / "result.json").exists())


if __name__ == "__main__":
    unittest.main()
