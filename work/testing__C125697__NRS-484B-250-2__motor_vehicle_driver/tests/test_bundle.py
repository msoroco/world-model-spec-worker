import json, unittest
from runner import validate_config
class BundleTest(unittest.TestCase):
 def test_exact_materialized_config(self):
  config=json.load(open("config.json"))
  self.assertEqual(validate_config(config)["selected_case_id"],config["selected_case_id"])
