import json, unittest
from pathlib import Path
from runner import load_config
class BundleTest(unittest.TestCase):
 def test_exact_materialized_config(self):
  config, site = load_config(Path('config.json'))
  self.assertEqual(config['selected_case_id'], 'testing__C125745__NRS-484B-250-2__motor_vehicle_driver__stop_ego_left_near_time')
  self.assertFalse(site.get('physical_acceptance_claimed', False))
