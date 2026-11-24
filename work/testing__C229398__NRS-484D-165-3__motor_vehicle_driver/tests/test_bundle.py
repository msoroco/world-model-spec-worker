import unittest
from runner import check
class BundleTest(unittest.TestCase):
    def test_exact_case_and_capture_profile(self):
        config=check()
        self.assertTrue(config["selected_case_id"].endswith("__"+config["case_key"]))
        self.assertEqual(len(config["cameras"]),4)
