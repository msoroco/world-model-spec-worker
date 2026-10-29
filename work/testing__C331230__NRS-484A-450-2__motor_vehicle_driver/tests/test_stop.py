import unittest
from pathlib import Path
from analyze import required
class StopTest(unittest.TestCase):
 def test_missing_physical_reference(self):
  with self.assertRaisesRegex(ValueError,"Missing required source: crosswalk_geometry.json"):required(Path("/nonexistent"),"crosswalk_geometry.json")
