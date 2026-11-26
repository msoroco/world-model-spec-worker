import unittest
import runner

class OriginalBundleTest(unittest.TestCase):
    def test_exact_source_bound_preflight(self):
        self.assertEqual(runner.check()['case_id'], runner.CASE_ID)

    def test_original_capture_arguments_required(self):
        from unittest.mock import patch
        with patch('sys.argv', ['runner.py']):
            with self.assertRaisesRegex(ValueError, 'original source and Native adapter'):
                runner.main()
