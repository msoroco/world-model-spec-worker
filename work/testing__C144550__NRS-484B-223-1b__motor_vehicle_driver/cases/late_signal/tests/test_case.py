import unittest
from pathlib import Path
from analyze import movement_event
from runner import check
class T(unittest.TestCase):
 def test_topology(self):self.assertTrue(check()['passed'])
 def test_missing(self):
  with self.assertRaisesRegex(ValueError,'Missing required source: scenario_geometry.json'):movement_event(Path('nonexistent'))
