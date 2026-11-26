import json
import unittest
from pathlib import Path
import runner
from geometry import check as road_check

class ExactConstruction(unittest.TestCase):
    def test_road_and_capture(self):
        self.assertTrue(runner.check()['passed'])
        self.assertTrue(road_check())
        config=json.loads(Path('config.json').read_text())
        self.assertEqual(config['selected_case_id'], config['case_id'])
        self.assertEqual(len(config['cameras']), 4)
    def test_lane_transition_and_speed_request(self):
        config=json.loads(Path('config.json').read_text())
        speed, lateral=runner.target(config['case_id'],-200,config['transition_m'])
        self.assertEqual(speed,config['requested_speed_mps'])
        self.assertLess(lateral,0)
