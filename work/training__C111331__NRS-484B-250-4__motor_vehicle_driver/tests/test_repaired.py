import unittest
from runner import check

class RepairedSource(unittest.TestCase):
    def test_geometry_and_request(self):
        result=check()
        self.assertEqual(result['frames'],600)
        self.assertFalse(result['native_signals_observed'])
