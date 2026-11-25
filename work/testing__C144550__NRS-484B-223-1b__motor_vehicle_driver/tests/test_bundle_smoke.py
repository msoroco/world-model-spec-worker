import unittest
from runner import check

class BundleSmoke(unittest.TestCase):
    def test_exact_case_and_capture(self):
        c = check()
        self.assertEqual(c['rate_hz'] * c['duration_s'], 900)
        self.assertEqual(c['selected_case_id'], 'testing__C144550__NRS-484B-223-1b__motor_vehicle_driver__both_observed')
