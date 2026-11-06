import json
from pathlib import Path
import unittest

from runner import check, frame_map_row


class RunnerCheck(unittest.TestCase):
    def test_exact_bundle(self):
        config_path = Path(__file__).resolve().parents[1] / 'config.json'
        if not config_path.is_file():
            self.skipTest('Exact config exists only in a materialized candidate bundle')
        config = json.loads(config_path.read_text())
        outcome = check(config)
        self.assertTrue(outcome['offline_geometry']['passed'])
        self.assertEqual(outcome['candidate_id'], config['candidate_id'])
        self.assertFalse(outcome['physical_success_claimed'])

    def test_join_rejects_invalid_identity(self):
        with self.assertRaises(ValueError):
            frame_map_row(1, -1, .05)


if __name__ == '__main__':
    unittest.main()
