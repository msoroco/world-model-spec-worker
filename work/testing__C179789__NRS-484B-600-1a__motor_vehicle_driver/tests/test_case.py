import unittest
from pathlib import Path
from analyze import traffic_speed,road_conditions,environment_history,required
class CaseTest(unittest.TestCase):
 def test_speed_traffic(self):
  self.assertEqual(traffic_speed({"motion_rows":[{"frame":1,"ego_speed_mps":4,"other_speed_mps":3,"separation_m":50}]})["max_ego_speed_mps"],4)
 def test_missing_packet(self):
  with self.assertRaisesRegex(ValueError,"Missing required source: case_observation.json"):required(Path("/nonexistent"),"case_observation.json")
