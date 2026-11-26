"""Bundled source-shaped CPU construction check; never imports CARLA."""
import unittest

from nonthrough_native_capture import check


class NativeCapturePlan(unittest.TestCase):
    def test_exact_selected_request_inventory(self):
        result = check()
        self.assertEqual(result['exact_case_count'], 10)
        self.assertFalse(result['carla_imported'])
        self.assertFalse(result['physical_acceptance_claimed'])
        self.assertTrue(all(row['frames'] == 600 for row in result['cases']))


if __name__ == '__main__':
    unittest.main()
