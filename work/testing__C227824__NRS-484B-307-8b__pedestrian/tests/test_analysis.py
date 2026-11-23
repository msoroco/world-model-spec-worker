import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]
OUTPUT = WORKSPACE / ".runtime-work" / "c227824-test-runtime"
OUTPUT.mkdir(parents=True, exist_ok=True)
os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(OUTPUT)
sys.path.insert(0, str(WORKSPACE / "runtime" / "scenario_pipeline"))
sys.path.insert(0, str(ROOT))

from analysis import finalize, main
from test_saved_entry import CASE, make_attempt


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        safe = WORKSPACE / ".runtime-work"
        safe.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=safe)
        self.root = Path(self.temp.name)
        make_attempt(self.root)
        scene = json.loads((self.root / "scene.json").read_text())
        scene["entry_request"] = "entry"
        (self.root / "scene.json").write_text(json.dumps(scene) + "\n")
        acquisition = json.loads((self.root / "acquisition.json").read_text())
        import hashlib
        acquisition["scene.json"]["sha256"] = hashlib.sha256(
            (self.root / "scene.json").read_bytes()).hexdigest()
        (self.root / "acquisition.json").write_text(json.dumps(acquisition) + "\n")
        self.description = {
            "channels": [{"name": name, "unit": "source_packet"} for name in
                         ("walker_body_history", "facing_signal_history",
                          "other_device_history", "camera_frame_map")],
            "context_inputs": [{"name": "highway_boundary", "unit": "m"}],
        }
        (self.root / "construction.json").write_text(json.dumps({
            "case_id": CASE, "recording_description": self.description}) + "\n")
        (self.root / "config.json").write_text(json.dumps({
            "selected_case_id": CASE, "law_id": "NRS-484B-307-8b",
            "cell_id": "C227824", "actor": "pedestrian", "duration_s": .15}) + "\n")
        (self.root / "trace.jsonl").write_text("".join(json.dumps({
            "frame": i + 1, "time_s": (i + 1) * .05,
            "position_m": [i, 3, 0]}) + "\n" for i in range(3)))

    def tearDown(self):
        self.temp.cleanup()

    def test_saved_result_and_channels_have_exact_source_links(self):
        report, result = finalize(self.root)
        self.assertTrue(report["analysis_complete"])
        self.assertTrue(result["measured_values"]["entry_observed"])
        self.assertTrue(result["target_checks"][0]["matched"])
        self.assertFalse(result["physical_acceptance_claimed"])
        self.assertEqual(len(result["recording_evidence"]), 5)
        self.assertEqual(result["provenance_kind"], "synthetic_fixture")
        self.assertFalse(report["legal_verdict_claimed"])

    def test_selected_case_mismatch_rejected(self):
        path = self.root / "config.json"
        config = json.loads(path.read_text())
        config["selected_case_id"] = CASE + "_changed"
        path.write_text(json.dumps(config) + "\n")
        with self.assertRaisesRegex(ValueError, "case differs"):
            finalize(self.root)

    def test_wait_request_with_observed_entry_does_not_match(self):
        import hashlib
        scene_path = self.root / "scene.json"
        scene = json.loads(scene_path.read_text())
        scene["entry_request"] = "wait"
        scene_path.write_text(json.dumps(scene) + "\n")
        acquisition_path = self.root / "acquisition.json"
        acquisition = json.loads(acquisition_path.read_text())
        acquisition["scene.json"]["sha256"] = hashlib.sha256(scene_path.read_bytes()).hexdigest()
        acquisition_path.write_text(json.dumps(acquisition) + "\n")
        report, result = finalize(self.root)
        self.assertTrue(report["measurement"]["entry_observed"])
        self.assertFalse(result["target_checks"][0]["matched"])

    def test_undeclared_channel_rejected(self):
        construction_path = self.root / "construction.json"
        construction = json.loads(construction_path.read_text())
        construction["recording_description"]["channels"].append(
            {"name": "invented_signal", "unit": "source_packet"})
        construction_path.write_text(json.dumps(construction) + "\n")
        with self.assertRaisesRegex(ValueError, "unsupported declared channel"):
            finalize(self.root)

    def test_cli_writes_result_and_report_once(self):
        output = self.root / "analysis-report.json"
        self.assertEqual(main(["--attempt", str(self.root), "--output", str(output)]), 0)
        self.assertTrue(output.is_file())
        self.assertTrue((self.root / "result.json").is_file())
        with self.assertRaises(FileExistsError):
            main(["--attempt", str(self.root), "--output", str(output)])


if __name__ == "__main__":
    unittest.main()
