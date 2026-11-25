"""Source-only construction checks; no simulator or legal claim."""
import json
import unittest
from pathlib import Path

import runner


class OneWayConstruction(unittest.TestCase):
    def test_exact_direction_and_capture_profile(self):
        config = json.loads(Path('config.json').read_text())
        checked = runner.check(config['requested_direction'])
        self.assertEqual(checked['frames'], 600)
        self.assertEqual(checked['rate_hz'], 20)
        self.assertEqual(len(checked['camera_names']), 4)
        self.assertEqual(checked['sign_request_ids'], [101, 102])
        self.assertFalse(checked['physical_acceptance_claimed'])

    def test_invalid_direction_rejected(self):
        with self.assertRaises(ValueError):
            runner.check('unselected')
