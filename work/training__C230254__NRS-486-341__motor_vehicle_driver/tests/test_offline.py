import json, unittest
from pathlib import Path
from runner import check
class Offline(unittest.TestCase):
 def test_exact(self):
  cfg=json.loads(Path("config.json").read_text())
  self.assertEqual(check(cfg)["frames"],600)
  self.assertEqual(cfg["case_id"],cfg["selected_case_id"])
