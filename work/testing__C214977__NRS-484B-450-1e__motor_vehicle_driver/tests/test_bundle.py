import json
from pathlib import Path
import unittest
class BundleTest(unittest.TestCase):
 def test_exact_identity(self):
  c=json.loads((Path(__file__).resolve().parents[1]/"config.json").read_text())
  self.assertEqual(c["case"]["case_id"],c["selected_case_id"])
  self.assertEqual(c["rate_hz"],20)
  self.assertEqual(len(c["cameras"]),4)
