"""Materialized exact-case Native preflight and missing-source checks."""

import json
from pathlib import Path
import unittest

from runner import check
from source_review import load


class RailCrossingNativeTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_exact_preflight(self):
        result = check(self.config)
        self.assertEqual(result['frames'], 600)
        self.assertFalse(result['simulation_started'])

    def test_missing_original_review_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'original grade-crossing review source missing'):
            load(Path('missing-original-review'), 'a'*64)

    def test_identity_and_camera_drift_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'identity'):
            check(dict(self.config, actor='rail_vehicle'))
        with self.assertRaisesRegex(ValueError, 'four original'):
            check(dict(self.config, cameras=self.config['cameras'][:3]))


if __name__ == '__main__':
    unittest.main()
