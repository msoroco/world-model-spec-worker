"""Saved diagnostic analysis checks source joins without physical claims."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import analyze


class AnalysisTest(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("construction.json", "config.json", "case-plan.json"):
            (self.root / name).write_bytes((ROOT / name).read_bytes())
        self.config = json.loads((self.root / "config.json").read_text())
        case = self.config["case"]
        context = {"case_id": case["case_id"],
                   "school_in_session_today": case["session_request"] == "session",
                   "time_window_label": case["time_request"],
                   "beacon_or_sign_state": case["beacon_or_sign_request"]}
        (self.root / "context.json").write_text(json.dumps(context) + "\n")
        rows = [{"frame": i, "time_s": i / 20,
                 "heavy_speed_mps": case["speed_target_mph"] / 2.2369362921,
                 "inside_designated_zone": True, "sign_limit_active": True,
                 "beacon_yellow_lights_lit": [True, False]} for i in range(3)]
        (self.root / "original-trace.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows))
        (self.root / "cameras.json").write_text("{}\n")
        (self.root / "trace.jsonl").write_text(
            "".join(json.dumps({"frame": i + 100, "time_s": i / 20}) + "\n"
                    for i in range(3)))
        (self.root / "video_frames.jsonl").write_text(
            "".join(json.dumps({"carla_frame": i + 100, "time_s": i / 20}) + "\n"
                    for i in range(3)))
        receipt = {"source_kind": "synthetic_diagnostic_fixture",
                   "diagnostic_fixture": True,
                   "assignment_id": self.config["assignment_id"],
                   "case_id": case["case_id"]}
        for key, name in (("context_sha256", "context.json"),
                          ("trace_sha256", "original-trace.jsonl"),
                          ("camera_manifest_sha256", "cameras.json")):
            receipt[key] = hashlib.sha256((self.root / name).read_bytes()).hexdigest()
        (self.root / "receipt.json").write_text(json.dumps(receipt) + "\n")
        (self.root / "fixture-provenance.json").write_text(
            '{"diagnostic_fixture":true}\n')

    def test_diagnostic_report_keeps_claims_unverified(self):
        report = analyze(self.root, self.root / "analysis-report.json")
        self.assertTrue(report["diagnostic_fixture"])
        result = json.loads((self.root / "result.json").read_text())
        self.assertFalse(result["physical_acceptance_claimed"])
        self.assertFalse(result["setup_confirmed"])
        self.assertEqual(result["target_checks"][0]["requested"],
                         self.config["case"]["speed_target_mph"])

    def test_missing_case_source_rejected(self):
        (self.root / "context.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source: context.json"):
            analyze(self.root, self.root / "analysis-report.json")


if __name__ == "__main__":
    unittest.main()
