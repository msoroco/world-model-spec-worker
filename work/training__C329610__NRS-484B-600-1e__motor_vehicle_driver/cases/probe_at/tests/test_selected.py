import json
import unittest
from pathlib import Path
import runner
from speed_turn import check_config

class SelectedSpeed(unittest.TestCase):
 def test_exact_construction(self):
  config=json.loads(Path('config.json').read_text())
  self.assertTrue(runner.check()['passed'])
  check_config(config,Path('road.xodr').read_text())
  self.assertIn(config['requested_speed_mph'],(75,80,85))
  self.assertEqual(runner.requested_speed(10,config['requested_speed_mph']),config['requested_speed_mph']*.44704)
 def test_wrong_scope(self):
  config=json.loads(Path('config.json').read_text())
  config['cell_id']='wrong'
  with self.assertRaises(ValueError):check_config(config,Path('road.xodr').read_text())
