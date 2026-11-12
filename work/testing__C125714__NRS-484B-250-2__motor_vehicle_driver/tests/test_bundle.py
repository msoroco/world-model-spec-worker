import json, unittest
from runner import validate_config
class BundleTest(unittest.TestCase):
 def test_reviewed_synthetic_bundle(self):
  config=json.load(open('config.json'))
  self.assertEqual(validate_config(config)['selected_case_id'],config['selected_case_id'])
