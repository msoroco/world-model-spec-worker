"""Outer-lane left/straight comparison from retained originals."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outer_nonapplicability_comparison_audit import audit
import test_turn_origin_comparison_audit
import test_straight_outer_source


class OuterNonapplicabilityComparisonTests(unittest.TestCase):
    def _pair(self, directory):
        left, straight = Path(directory)/'left', Path(directory)/'straight'
        left.mkdir(); straight.mkdir()
        test_turn_origin_comparison_audit.side(left, outer=True)
        test_straight_outer_source.StraightOuterSourceTests()._source(straight)
        return left, straight

    def test_outer_lane_held_fixed_across_maneuvers(self):
        with tempfile.TemporaryDirectory() as directory:
            left, straight = self._pair(directory)
            proof = audit(left, straight, decode_video=False)
            self.assertEqual(proof['comparison_id'], 'outer_nonapplicability')
            self.assertTrue(proof['outer_lane_outside_candidate_center_in_both'])

    def test_center_entry_rejects_outer_control(self):
        with tempfile.TemporaryDirectory() as directory:
            left, straight = self._pair(directory)
            path = straight/'turn_origin_native.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            for row in rows:
                row['lane_id'] = 1
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'entered candidate center'):
                audit(left, straight, decode_video=False)
