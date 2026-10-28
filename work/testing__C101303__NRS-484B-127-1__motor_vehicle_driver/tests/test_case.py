import json
import subprocess
import sys
import unittest
from pathlib import Path
import runner
from scenario import lane_path
class CaseTests(unittest.TestCase):
 def test_exact_geometry_and_capture_contract(self):
  runner.check()
  cfg=json.loads(Path("config.json").read_text())
  self.assertEqual(cfg["selected_case_id"],cfg["case"]["case_id"])
  self.assertGreater(len(lane_path(cfg)),100)
 def test_analysis_entrypoint_resolves(self):
  result=subprocess.run([sys.executable,"analyze.py","--help"],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
