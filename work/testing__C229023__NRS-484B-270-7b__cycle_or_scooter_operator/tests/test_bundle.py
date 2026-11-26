"""Portable source-gated bundle smoke and original-source rejection."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overtake import CASES
from runner import ASSIGNMENT, VIEWS, load_scene

BUNDLE = Path(__file__).resolve().parents[1]


class BundleTest(unittest.TestCase):
    def test_exact_capture_config(self):
        config = json.loads((BUNDLE / 'config.json').read_text())
        self.assertIn(config['selected_case_id'],
                      [ASSIGNMENT + '__' + item.case_id for item in CASES])
        self.assertEqual(config['frame_count'], 900)
        self.assertEqual(config['rate_hz'], 20)
        self.assertEqual(tuple(x['name'] for x in config['cameras']), VIEWS)

    def test_missing_reviewed_packet_rejected(self):
        config = json.loads((BUNDLE / 'config.json').read_text())
        case = next(item for item in CASES if
                    config['selected_case_id'] == ASSIGNMENT + '__' + item.case_id)
        with self.assertRaises(FileNotFoundError):
            load_scene(Path('nonexistent-review-packet.json'), Path('.'), case)


if __name__ == '__main__':
    unittest.main()
