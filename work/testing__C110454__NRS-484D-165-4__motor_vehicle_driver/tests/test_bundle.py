import os
import unittest
from unittest.mock import patch
import runner


class SelectedBundleTests(unittest.TestCase):
    def test_exact_selected_identity(self):
        self.assertTrue(runner.check().startswith('testing__C110454__NRS-484D-165-4__motor_vehicle_driver__'))

    def test_refuses_unreviewed_site(self):
        with patch.dict(os.environ, {'PARKED_HEADLAMP_SITE_PACKET': ''}), \
             patch('sys.argv', ['runner.py', '--output-dir', 'attempt']):
            with self.assertRaisesRegex(ValueError, 'SITE_PACKET'):
                runner.main()


if __name__ == '__main__':
    unittest.main()
