import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_posted_speed as _source


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
CASE = ROOT.name + "__posted_below"


class FinalizerTests(unittest.TestCase):
    def fixture(self, attempt):
        _source.PostedSpeedTests().fixture(attempt, 24.9)
        (attempt / "capture").mkdir()
        (attempt / "capture/evidence.jsonl").write_text('{"frame":100}\n')
        (attempt / "trace.jsonl").write_text("".join(json.dumps(
            {"frame": 100 + i, "time_s": 1 + i * .05,
             "position_m": [i * 2, 0, 0], "speed_mps": 24.9 * .44704}) + "\n"
            for i in range(3)))
        for name in ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"):
            (attempt / name).write_bytes(b"textual video placeholder")
        config = {"selected_case_id": CASE, "law_id": "NRS-484B-600-1c",
                  "cell_id": "C136559", "actor": "motor_vehicle_driver",
                  "duration_s": .15, "rate_hz": 20, "requested_speed_mph": 24.9,
                  "recording_description": {"channels": [{"name": "kin.speed"}]}}
        (attempt / "config.json").write_text(json.dumps(config))

    def command(self, attempt):
        env = dict(os.environ, PYTHONPATH=str(REPO / "runtime/scenario_pipeline"))
        return subprocess.run([sys.executable, str(ROOT / "finalizer.py"),
                               "--attempt", str(attempt), "--output", str(attempt / "analysis-report.json")],
                              capture_output=True, text=True, env=env)

    def test_saved_posted_measurement_uses_original_signed_zone(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt = Path(temp)
            self.fixture(attempt)
            run = self.command(attempt)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads((attempt / "result.json").read_text())
            self.assertAlmostEqual(result["measured_values"]["sampled_peak_in_zone_mph"], 24.9)
            self.assertEqual(result["measured_values"]["posted_limit_mph"], 25)
            self.assertFalse(result["measured_values"]["sampled_peak_greater_than_posted"])
            self.assertFalse(result["physical_acceptance_claimed"])
            self.assertNotIn("legal_verdict", result)
            sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
            from worker_exchange.measurement_contract import validate, verify_report
            contract = json.loads((ROOT / "measurement-contract.json").read_text())
            plan = json.loads((ROOT / "case-plan.json").read_text())
            report = json.loads((attempt / "analysis-report.json").read_text())
            validate(contract, plan["requirement_dispositions"],
                     (ROOT / "finalizer.py").read_text(), CASE)
            verify_report(contract, report, attempt)

    def test_missing_governance_source_rejected_without_result(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt = Path(temp)
            self.fixture(attempt)
            (attempt / "sign_context.json").unlink()
            run = self.command(attempt)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("Missing required source: sign_context.json", run.stderr)
            self.assertFalse((attempt / "result.json").exists())


if __name__ == "__main__":
    unittest.main()
