import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class RootPackage(unittest.TestCase):
    def test_all_selected_cases_and_camera_timing(self):
        plan = json.loads((ROOT / "case-plan.json").read_text())
        config = json.loads((ROOT / "config.json").read_text())
        self.assertEqual(set(config["supported_case_ids"]), {case["case_id"] for case in plan["cases"]})
        self.assertEqual(plan["camera_plan"]["duration_s"], config["duration_s"])
        self.assertEqual([x["name"] for x in config["cameras"]], ["overview", "approach", "reference_corner", "driver_reference"])

    def test_runner_imports_current_runtime_only(self):
        runner = (ROOT / "runner.py").read_text()
        self.assertNotIn("runtime/pipeline", runner)
        self.assertIn("runtime/scenario_pipeline", runner)
        result = subprocess.run([sys.executable, str(ROOT / "runner.py"), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
