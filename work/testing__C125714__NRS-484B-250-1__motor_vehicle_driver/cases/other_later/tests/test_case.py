import unittest,tempfile
from pathlib import Path
from runner import check
from analyze import finalize
class T(unittest.TestCase):
 def test_structure(self):self.assertTrue(check()['passed'])
 def test_missing(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaisesRegex(ValueError,'Missing required source: case_observation.json'):finalize(Path(t),Path(t)/'analysis-report.json')
