import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from test_observed_speed import SCRATCH, fixture

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("finalize", ROOT / "finalize.py")
module = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(ROOT))
spec.loader.exec_module(module)


class SavedFinalizerTest(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.attempt = Path(self.temp.name) / "attempt"
        self.attempt.mkdir()
        rows = fixture("a")
        (self.attempt / "emergency_observations.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
        (self.attempt / "video_frames.jsonl").write_text(
            "".join(json.dumps({"native_frame": row["native_frame"],
                                 "time_s": row["time_s"]}) + "\n" for row in rows))
        (self.attempt / "trace.jsonl").write_text(
            "".join(json.dumps({"native_frame": row["native_frame"]}) + "\n" for row in rows))
        (self.attempt / "capture").mkdir()
        (self.attempt / "capture/manifest.json").write_text("{}\n")
        (self.attempt / "acquisition-provenance.json").write_text(
            json.dumps({"diagnostic_fixture": True, "provenance_kind": "synthetic"}) + "\n")
        construction = json.loads((ROOT / "selected/a/construction.json").read_text())
        (self.attempt / "construction.json").write_text(json.dumps(construction) + "\n")
        config = next(json.loads(file["content"]) for file in construction["files"]
                      if file["path"] == "config.json")
        (self.attempt / "config.json").write_text(json.dumps(config) + "\n")
        for video in module.VIDEOS:
            (self.attempt / video).write_bytes(b"synthetic placeholder; no media claim")
        self.output = self.attempt / "analysis-report.json"
        os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH)
        sys.path.insert(0, str(ROOT.parents[2] / "runtime"))
        sys.path.insert(0, str(ROOT.parents[2] / "runtime/scenario_pipeline"))

    def test_saved_positive_has_no_physical_or_legal_claim(self):
        report = module.finalize(self.attempt, self.output)
        self.assertTrue(report["fixture_only"])
        self.assertFalse(report["physical_acceptance_claimed"])
        result = json.loads((self.attempt / "result.json").read_text())
        self.assertFalse(result["setup_confirmed"])
        self.assertFalse(result["accepted"])
        from scenario_pipeline.worker_exchange.measurement_contract import validate, verify_report
        contract = json.loads((ROOT / "selected/a/measurement-contract.json").read_text())
        plan = json.loads((ROOT.parent / "case-plan.json").read_text())
        validate(contract, plan["requirement_dispositions"], (ROOT / "finalize.py").read_text(),
                 result["case_id"])
        self.assertEqual(len(verify_report(contract, report, self.attempt)), 2)

    def test_missing_case_source_rejected(self):
        (self.attempt / "emergency_observations.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source: emergency_observations.jsonl"):
            module.finalize(self.attempt, self.output)

    def test_saved_derived_channel_must_match_source(self):
        module.finalize(self.attempt, self.output)
        self.output.unlink()
        (self.attempt / "result.json").unlink()
        (self.attempt / "emergency_speed_and_lamps.jsonl").write_text("forged\n")
        with self.assertRaisesRegex(ValueError, "Saved derived channel differs"):
            module.finalize(self.attempt, self.output)

    def test_original_claim_without_seal_rejected(self):
        (self.attempt / "acquisition-provenance.json").write_text(
            json.dumps({"diagnostic_fixture": False, "provenance_kind": "native"}) + "\n")
        with self.assertRaisesRegex(ValueError, "Original Native capture seal missing"):
            module.finalize(self.attempt, self.output)


if __name__ == "__main__":
    unittest.main()
