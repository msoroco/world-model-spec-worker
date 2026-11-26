import json
import unittest
from pathlib import Path
import runner

class SelectedCrossing(unittest.TestCase):
 def test_exact_native_request(self):
  config=json.loads(Path('config.json').read_text())
  self.assertTrue(runner.check(config)['passed'])
  self.assertEqual(runner.request(config['pedestrian_departure_frame']-1, config['case_id'])['pedestrian_target_speed_mps'],0)
  self.assertGreater(runner.request(config['pedestrian_departure_frame'], config['case_id'])['pedestrian_target_speed_mps'],0)
 def test_wrong_case_rejected(self):
  config=json.loads(Path('config.json').read_text())
  config['case_id']='wrong'
  with self.assertRaises(ValueError):runner.check(config)
