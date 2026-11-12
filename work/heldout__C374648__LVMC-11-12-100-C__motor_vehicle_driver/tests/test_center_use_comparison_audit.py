"""Independent center-lane turn/straight comparison checks."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from center_use_comparison_audit import audit
import test_straight_center_source
import test_turn_origin_comparison_audit


class CenterUseComparisonTests(unittest.TestCase):
    def _pair(self, directory):
        left, straight = Path(directory)/'left', Path(directory)/'straight'
        left.mkdir(); straight.mkdir()
        test_turn_origin_comparison_audit.side(left)
        test_straight_center_source.StraightCenterSourceTests()._source(straight)
        return left, straight

    def test_center_lane_held_fixed_across_maneuvers(self):
        with tempfile.TemporaryDirectory() as directory:
            left, straight = self._pair(directory)
            proof = audit(left, straight, decode_video=False)
            self.assertEqual(proof['comparison_id'], 'center_use')
            self.assertEqual(proof['observed_difference']['left_maneuver'], 'left turn')
            self.assertEqual(proof['observed_difference']['straight_maneuver'], 'straight')
            self.assertFalse(proof['physical_acceptance_claimed'])

    def test_changed_center_origin_rejects(self):
        with tempfile.TemporaryDirectory() as directory:
            left, straight = self._pair(directory)
            path = straight/'turn_origin_native.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            for row in rows:
                row['lane_id'] = 2
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'fixed source'):
                audit(left, straight, decode_video=False)
