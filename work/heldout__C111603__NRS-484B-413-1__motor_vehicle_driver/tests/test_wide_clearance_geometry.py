"""The selected wide diagnostic must actually separate the sampled bodies."""

import json
from pathlib import Path
import sys
import unittest


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from comparison_audit import minimum_gap


class WideClearanceGeometryTests(unittest.TestCase):
    def test_positive_gap_and_fixed_ego_motion(self):
        base = json.loads((HERE / 'vehicle-indicator-diagnostic.json').read_text())['files']
        wide = json.loads((HERE / 'clearance-wide-diagnostic.json').read_text())['files']
        self.assertLess(minimum_gap(base), 0)
        self.assertGreater(minimum_gap(wide), 0)
        self.assertEqual(base['ego_turn_motion.jsonl'], wide['ego_turn_motion.jsonl'])
        self.assertEqual(base['trace.jsonl'], wide['trace.jsonl'])
        self.assertNotEqual(base['participant_bodies.jsonl'], wide['participant_bodies.jsonl'])


if __name__ == '__main__':
    unittest.main()
