import unittest
from pathlib import Path
from analyze import approach_path,indicator_continuity,required
class CaseTest(unittest.TestCase):
 def test_last_100_feet_bracket(self):
  p={"path_rows":[{"x_m":0,"y_m":0},{"x_m":20,"y_m":0},{"x_m":40,"y_m":0}],"turn_onset_frame":3}
  self.assertGreaterEqual(approach_path(p)["last_100ft_sampled_distance_m"],30.48)
 def test_missing_packet(self):
  with self.assertRaisesRegex(ValueError,"Missing required source: case_observation.json"):required(Path("/nonexistent"),"case_observation.json")
