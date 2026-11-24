import os
import json
import io
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import analysis
from crosswalk_measurements import ASSIGNMENT_ID


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.case_id = ASSIGNMENT_ID + "__unmarked_wait"
        for name in analysis.SOURCES:
            (self.root / name).write_bytes(name.encode())

    def test_source_bound_analysis_and_negative(self):
        measurement = {"case_id": self.case_id,
                       "measured_values": {"rear_approach_frames": [10]},
                       "observed": {"rear_approach_sampled": True},
                       "target_checks": [], "legal_judgment": "unresolved"}
        with patch.object(analysis, "finalize", return_value=measurement), patch.object(
                analysis, "build_result", return_value={"case_id": self.case_id}):
            report = analysis.run(self.root, self.root / "analysis-report.json", self.case_id)
        self.assertTrue(report["analysis_complete"])
        self.assertEqual(json.loads((self.root / "result.json").read_text())["case_id"], self.case_id)
        self.assertEqual(set(report["measurements"]["crosswalk_observation"]["sources"]), set(analysis.SOURCES))
        (self.root / "analysis-report.json").unlink()
        (self.root / "result.json").unlink()
        (self.root / "context.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source: context.json"):
            analysis.run(self.root, self.root / "analysis-report.json", self.case_id)

    def test_runtime_cli_derives_exact_case_from_materialized_config(self):
        (self.root / "config.json").write_text(json.dumps({"selected_case_id": self.case_id}))
        measurement = {"case_id": self.case_id, "measured_values": {"lead_stopped_frames": [20]},
                       "observed": {"lead_stop_sampled": True}, "target_checks": []}
        argv = ["analysis.py", "--attempt", str(self.root), "--output",
                str(self.root / "analysis-report.json")]
        with patch("sys.argv", argv), patch.object(analysis, "finalize", return_value=measurement), patch.object(
                analysis, "build_result", return_value={"case_id": self.case_id}), redirect_stdout(io.StringIO()):
            analysis.main()
        report = json.loads((self.root / "analysis-report.json").read_text())
        self.assertEqual(report["case_id"], self.case_id)


if __name__ == "__main__":
    unittest.main()
