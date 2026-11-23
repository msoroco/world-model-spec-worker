import unittest
from pathlib import Path
from runner import load_config,CASE
class BundleTest(unittest.TestCase):
 def test_exact_crosswalk_case(self):
  cfg,site=load_config(Path('.'))
  self.assertEqual(cfg['selected_case_id'],CASE)
  self.assertEqual(site['crosswalk_origin'],'marked')
  self.assertFalse(site['physical_acceptance_claimed'])
