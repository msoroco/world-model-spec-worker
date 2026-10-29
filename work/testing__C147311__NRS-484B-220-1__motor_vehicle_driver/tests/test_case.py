import unittest
from pathlib import Path
from analyze import direction_projection,sign_scope
class CaseTest(unittest.TestCase):
 def test_projection(self):
  self.assertEqual(direction_projection({"designated_direction_xy":[1,0],"velocity_rows":[{"frame":1,"velocity_xy":[-3,0]}]})["signed_projections_mps"],[-3])
 def test_missing_packet(self):
  from analyze import required
  with self.assertRaisesRegex(ValueError,"Missing required source: case_observation.json"):required(Path("/nonexistent"),"case_observation.json")
