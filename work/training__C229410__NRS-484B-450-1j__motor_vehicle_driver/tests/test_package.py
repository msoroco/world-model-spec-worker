import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PackageTests(unittest.TestCase):
    def test_native_preflight_is_cpu_only(self):
        call = subprocess.run([sys.executable, "runner.py", "--check"], cwd=ROOT,
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(call.returncode, 0, call.stderr)
        self.assertIn("native_imported", call.stdout)

    def test_selected_case_set_and_source_plan(self):
        config = json.loads((ROOT / "config.json").read_text())
        plan = json.loads((ROOT / "case-plan.json").read_text())
        self.assertEqual(set(config["supported_case_ids"]),
                         {case["case_id"] for case in plan["cases"]})
        self.assertEqual(len(plan["camera_plan"]["coverage"]), 4)
        self.assertEqual(len(plan["comparisons"]), 10)

if __name__ == "__main__":
    unittest.main()
