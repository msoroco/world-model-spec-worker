import unittest
from pathlib import Path
from analyze import turn_trajectory,median_geometry,required
class CaseTest(unittest.TestCase):
 def test_direction_reversal_measurement(self):
  p={"trajectory":[{"frame":1,"velocity_xy":[2,0],"body_overlaps_median":False},{"frame":2,"velocity_xy":[-2,0],"body_overlaps_median":True}]}
  self.assertEqual(turn_trajectory(p)["direction_dot"],-4)
 def test_missing_packet(self):
  with self.assertRaisesRegex(ValueError,"Missing required source: case_observation.json"):required(Path("/nonexistent"),"case_observation.json")
