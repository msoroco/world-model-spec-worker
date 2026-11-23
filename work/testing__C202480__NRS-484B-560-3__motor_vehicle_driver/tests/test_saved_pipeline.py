"""Require closed ownership before the saved postcapture phase."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from saved_pipeline import process


class SavedPipelineTests(unittest.TestCase):
    def setUp(self):
        private = ROOT / ".runtime-work"
        private.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=private)
        self.addCleanup(self.temp.cleanup)
        self.attempt = Path(self.temp.name) / "attempt"
        self.attempt.mkdir()
        self.status = {"errors": [], "capture": {"frames": 900},
                       "restoration": {"restored": True},
                       "retained_site_packet": "site/packet.json"}

    def write_status(self):
        (self.attempt / "native-run-status.json").write_text(json.dumps(self.status))

    def test_closed_status_runs_media_before_saved_analysis(self):
        self.write_status()
        order = []
        def media(path):
            self.assertEqual(path, self.attempt)
            order.append("media")
            return {"frames": 900}
        def measurement(path, output):
            self.assertEqual(output, self.attempt / "analysis-report.json")
            order.append("analysis")
            return {"legal_judgment": "unresolved"}
        result = process(self.attempt, media_finalizer=media,
                         measurement_finalizer=measurement)
        self.assertEqual(order, ["media", "analysis"])
        self.assertEqual(result["saved_report"]["legal_judgment"], "unresolved")

    def test_failed_or_unrestored_native_attempt_never_encodes(self):
        for change in ({"errors": ["capture failed"]},
                       {"restoration": {"restored": False}},
                       {"capture": {"frames": 899}}):
            with self.subTest(change=change):
                self.status.update(change)
                self.write_status()
                with self.assertRaisesRegex(ValueError, "closed original Native"):
                    process(self.attempt, media_finalizer=lambda _: self.fail("encoded"))
                self.status = {"errors": [], "capture": {"frames": 900},
                               "restoration": {"restored": True},
                               "retained_site_packet": "site/packet.json"}


if __name__ == "__main__":
    unittest.main()
