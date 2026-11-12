import unittest
from pathlib import Path
from runner import load_config,ASSIGNMENT
class BundleTest(unittest.TestCase):
 def test_exact_selected_config_and_site(self):
  config,site=load_config(str(Path(__file__).resolve().parents[1] / "config.json"))
  self.assertEqual(config["selected_case_id"],ASSIGNMENT+"__yield_ego_left_near_time")
  self.assertEqual(site["review_status"],"reviewed_candidate")
