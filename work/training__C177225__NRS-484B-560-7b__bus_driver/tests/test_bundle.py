import json
import unittest
from pathlib import Path
from runner import check
from rail_road import validate_authored_road
from officer_direction import Crossing

class BundleTest(unittest.TestCase):
    def test_exact_materialized_reference(self):
        config=json.loads(Path('config.json').read_text())
        result=check(config['case_suffix'],config['direction'],config)
        self.assertEqual(config['case_id'],result['case_id'])
        self.assertEqual([-1,1],validate_authored_road()['driving_lane_ids'])
        self.assertLess(Crossing().stop_station(1),Crossing().exit_station(1))
        self.assertFalse(result['physical_success_claimed'])
