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
from owner_release import release, sha


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
                       "case_id": "synthetic-case",
                       "native_process": {"pid": 99999999, "proc_start_ticks": 1},
                       "retained_site_packet": "site/packet.json"}

    def write_status(self):
        status_path = self.attempt / "native-run-status.json"
        status_path.write_text(json.dumps(self.status))
        (self.attempt / "native-exit.json").write_text(json.dumps({
            "event": "native_exit_pending_process_termination",
            "case_id": self.status["case_id"],
            "native_process": self.status["native_process"],
            "native_run_status_sha256": sha(status_path)}))
        (self.attempt / "owner-release.json").unlink(missing_ok=True)
        if self.status["errors"] == [] and self.status["capture"]["frames"] == 900 and self.status["restoration"]["restored"]:
            release(self.attempt, liveness_probe=lambda _: False)

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
        def decode(path):
            self.assertEqual(path, self.attempt)
            order.append("decode")
            return {"frames": 900}
        def geometry(path):
            self.assertEqual(path, self.attempt)
            order.append("geometry")
            return {"physical_acceptance_claimed": False}
        result = process(self.attempt, media_finalizer=media,
                         measurement_finalizer=measurement,
                         geometry_auditor=geometry,
                         source_decoder=decode)
        self.assertEqual(order, ["media", "decode", "analysis", "geometry"])
        self.assertEqual(result["saved_report"]["legal_judgment"], "unresolved")
        self.assertFalse(json.loads((self.attempt / "geometry-audit.json").read_text())
                         ["physical_acceptance_claimed"])

    def test_failed_or_unrestored_native_attempt_never_encodes(self):
        for change in ({"errors": ["capture failed"]},
                       {"restoration": {"restored": False}},
                       {"capture": {"frames": 899}}):
            with self.subTest(change=change):
                self.status.update(change)
                self.write_status()
                with self.assertRaisesRegex(ValueError, "Native"):
                    process(self.attempt, media_finalizer=lambda _: self.fail("encoded"))
                self.status = {"errors": [], "capture": {"frames": 900},
                               "restoration": {"restored": True},
                               "case_id": "synthetic-case",
                               "native_process": {"pid": 99999999,
                                                  "proc_start_ticks": 1},
                               "retained_site_packet": "site/packet.json"}


if __name__ == "__main__":
    unittest.main()
