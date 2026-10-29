import unittest
from pathlib import Path
from analyze import crossing_geometry,earlier_entry,required
class CaseTest(unittest.TestCase):
 def test_missing_packet(self):
  with self.assertRaisesRegex(ValueError,"Missing required source: case_observation.json"):required(Path("/nonexistent"),"case_observation.json")
 def test_case_method(self):
  self.assertTrue(callable(earlier_entry))
