import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from runner import AID
from test_audit_arm_cases import case_fixture
from test_finalize_sources import SCRATCH


REPO = Path.cwd()
FINALIZER = Path(__file__).resolve().parent.parent / "finalize.py"


class TestCanonicalFinalizer(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.root = Path(self.temp.name)
        case_fixture(self.root, "right_horizontal")
        case_id = AID + "__probe_a"
        (self.root / "config.json").write_text(json.dumps({
            "selected_case_id": case_id,
            "recording_description": {"channels": [{"name": "rider_arm_pose",
                                                 "unit": "source geometry"}],
                                      "context_inputs": []}}) + "\n")
        sources = [json.loads(line) for line in
                   (self.root / "rider_arm.jsonl").read_text().splitlines()]
        (self.root / "capture").mkdir()
        for name, rows in (
            ("trace.jsonl", [{"frame": row["native_frame"]} for row in sources]),
            ("video_frames.jsonl", [{"video_frame": i,
                "native_frame": row["native_frame"], "time_s": i / 20,
                "camera_native_frames": {camera: row["native_frame"]
                                         for camera in ("overview", "approach",
                                                        "reference_corner", "driver_reference")}}
                for i, row in enumerate(sources)]),
            ("capture/evidence.jsonl", [{"original_frame": row["native_frame"]}
                                       for row in sources]),
        ):
            (self.root / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
        for name in ("overview", "approach", "reference_corner", "driver_reference"):
            (self.root / (name + ".mkv")).write_text("diagnostic placeholder\n")
        self.env = os.environ.copy()
        self.env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH)
        self.env["PYTHONPATH"] = str(REPO / "runtime/scenario_pipeline")

    def tearDown(self):
        self.temp.cleanup()

    def test_source_join_writes_canonical_result_and_report(self):
        report = self.root / "analysis-report.json"
        result = subprocess.run([sys.executable, str(FINALIZER), "--attempt",
            str(self.root), "--output", str(report)], env=self.env,
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        analyzed = json.loads(report.read_text())
        native = json.loads((self.root / "result.json").read_text())
        self.assertEqual(analyzed["measurements"]["rider_arm_method_observation"]
                         ["value"]["right_observed_frames_in_window"], 40)
        self.assertEqual(native["target_checks"][0]["measured"], 40)
        self.assertFalse(native["physical_acceptance_claimed"])
        self.assertEqual(len((self.root / "channels/rider_arm_pose.jsonl").read_text().splitlines()), 600)

    def test_missing_case_source_and_frame_join_rejected(self):
        (self.root / "rider_arm.jsonl").unlink()
        result = subprocess.run([sys.executable, str(FINALIZER), "--attempt",
            str(self.root), "--output", str(self.root / "report.json")], env=self.env,
            capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing required source: rider_arm.jsonl", result.stderr)


if __name__ == "__main__":
    unittest.main()
