"""Materialized exact-case CPU test used by every inline construction."""
import json
import unittest
from pathlib import Path

import runner
from case_observation import PREFIX, SUFFIXES


class BundleTest(unittest.TestCase):
    def test_exact_binding_and_capture_sources(self):
        result = runner.check()
        self.assertIn(result['case_id'], [PREFIX + name for name in SUFFIXES])
        self.assertFalse(result['physical_acceptance_claimed'])
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(config['supported_case_ids'], [PREFIX + name for name in SUFFIXES])
        self.assertEqual(config['source_packets'], [])
        self.assertEqual(config['required_atoms'], [])

    def test_native_capture_import_is_cpu_lazy(self):
        from native_capture import CAMERAS
        self.assertEqual(CAMERAS, ('overview', 'approach', 'reference_corner', 'driver_reference'))


if __name__ == '__main__':
    unittest.main()
