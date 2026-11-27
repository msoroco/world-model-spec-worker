import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_night_parking_measurement import NightParkingMeasurementTests

ROOT = Path(__file__).resolve().parents[1]


class AnalysisTests(unittest.TestCase):
    def test_saved_analysis_and_missing_required_original(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work") as tmp:
            root = Path(tmp)
            contract, _ = NightParkingMeasurementTests()._fixture(root)
            (root / "night-parking-sources.json").write_text(json.dumps(dict(format="night-parking-original-sources-v1", **contract)) + "\n")
            (root / "config.json").write_text(json.dumps({"selected_case_id": "exact", "parking_duration_s": 1}) + "\n")
            names = ("original_body_state", "other_vehicle_body_state", "civil_time", "vehicle_classification", "parking_activity", "street_jurisdiction")
            channels = [{"name": name, "unit": "structured record"} for name in names]
            (root / "construction.json").write_text(json.dumps({"case_id": "exact", "recording_description": {"channels": channels, "context_inputs": [], "limitations": []}}) + "\n")
            command = [sys.executable, str(ROOT / "analysis.py"), "--attempt", str(root), "--output", str(root / "analysis-report.json")]
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            positive = subprocess.run(command, text=True, capture_output=True, env=env)
            self.assertEqual(positive.returncode, 0, positive.stderr)
            result = json.loads((root / "result.json").read_text())
            report = json.loads((root / "analysis-report.json").read_text())
            self.assertEqual(result["case_id"], "exact")
            self.assertEqual(report["measurements"]["nighttime_parking_episode"]["value"]["elapsed_s"], 1)
            self.assertEqual(len(result["recording_evidence"]), 6)
            self.assertFalse(result["physical_acceptance_claimed"])
            self.assertFalse(report["legal_verdict_claimed"])
            (root / "result.json").unlink()
            (root / "classification.json").unlink()
            negative = subprocess.run(command, text=True, capture_output=True, env=env)
            self.assertNotEqual(negative.returncode, 0)
            self.assertIn("Missing required source: classification.json", negative.stderr)


if __name__ == "__main__":
    unittest.main()
