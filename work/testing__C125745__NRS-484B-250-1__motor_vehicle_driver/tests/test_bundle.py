import json
import unittest
from pathlib import Path
import runner
from stop_sign_control import load_site
from source_cameras import CAMERAS
from crossing_measurements import finalize_saved
import tempfile
class BundleTest(unittest.TestCase):
 def test_exact_cpu_bundle(self):
  site=runner.check_plan(Path("case-plan.json"),Path("config.json"))
  self.assertEqual(site["stop_sign_native_id"],17)
  self.assertEqual(set(site["camera_poses"]),set(CAMERAS))
  self.assertEqual(json.loads(Path("config.json").read_text())["selected_case_id"],runner.CASE)
  with tempfile.TemporaryDirectory() as temp:
   with self.assertRaisesRegex(ValueError,"Missing required source"):
    finalize_saved(Path(temp),Path(temp)/"analysis.json")
