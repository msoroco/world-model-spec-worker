"""Original-source east/west controlled direction checks."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from east_direction_comparison_audit import audit
import test_turn_origin_comparison_audit
import test_west_turn_origin_comparison_audit


class EastDirectionComparisonTests(unittest.TestCase):
    def _pair(self, directory):
        east, west = Path(directory)/'east', Path(directory)/'west'
        east.mkdir(); west.mkdir()
        test_turn_origin_comparison_audit.side(east)
        test_west_turn_origin_comparison_audit.west_side(west)
        return east, west

    def test_opposed_original_headings_with_center_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            east, west = self._pair(directory)
            proof = audit(east, west, decode_video=False)
            self.assertEqual(proof['comparison_id'], 'east_direction')
            self.assertEqual(proof['observed_difference']['east_origin_lane_id'], 1)
            self.assertEqual(proof['observed_difference']['west_origin_lane_id'], -1)

    def test_same_original_heading_rejects(self):
        with tempfile.TemporaryDirectory() as directory:
            east, west = self._pair(directory)
            path = west/'turn_origin_native.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            for row in rows:
                row['ego_forward_xy'] = [-v for v in row['ego_forward_xy']]
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'direction did not change'):
                audit(east, west, decode_video=False)
