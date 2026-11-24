import unittest
from check import check


class ExactRequestTests(unittest.TestCase):
    def test_frozen_source_and_requested_track(self):
        result = check()
        self.assertTrue(result['passed'])
        self.assertEqual(result['frames'], 600)
        self.assertFalse(result['native_observed'])
        self.assertFalse(result['driver_view_nearest_point_proven'])
        self.assertIsNone(result['legal_verdict'])
