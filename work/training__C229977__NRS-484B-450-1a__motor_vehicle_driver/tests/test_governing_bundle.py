"""Portable exact governing-law request checks for materialized bundles."""
import json
from pathlib import Path
import unittest

import runner


class GoverningBundleTests(unittest.TestCase):
    def test_exact_native_config(self):
        config = json.loads(Path('config.json').read_text())
        result = runner.check(config)
        self.assertEqual(result['frames'], 600)
        self.assertTrue(result['case_id'].endswith(('__governing_law_absent', '__governing_law_present')))

    def test_sidewalk_request_and_case_isolation(self):
        config = json.loads(Path('config.json').read_text())
        request = runner.request(180, config['case_id'])
        self.assertTrue(request['requested_sidewalk_occupancy'])
        with self.assertRaises(ValueError):
            runner.request(180, config['case_id'].replace('governing_law', 'official_device'))


if __name__ == '__main__':
    unittest.main()
