"""Independent straight center-use comparison checks."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from center_use_comparison_audit import audit
import test_straight_center_source
import test_straight_outer_source


class CenterUseComparisonTests(unittest.TestCase):
    def _pair(self, directory):
        center, outer = Path(directory)/'center', Path(directory)/'outer'
        center.mkdir(); outer.mkdir()
        test_straight_center_source.StraightCenterSourceTests()._source(center)
        test_straight_outer_source.StraightOuterSourceTests()._source(outer)
        return center, outer

    def test_straight_origin_difference_from_originals(self):
        with tempfile.TemporaryDirectory() as directory:
            center, outer = self._pair(directory)
            proof = audit(center, outer, decode_video=False)
            self.assertEqual(proof['comparison_id'], 'center_use')
            self.assertEqual(proof['observed_difference'],
                             {'center_origin_lane_id': 1, 'outer_origin_lane_id': 2})
            self.assertFalse(proof['physical_acceptance_claimed'])

    def test_changed_straight_target_road_rejects(self):
        with tempfile.TemporaryDirectory() as directory:
            center, outer = self._pair(directory)
            path = outer/'case_context.json'
            context = json.loads(path.read_text())
            context['target_exit_road_id'] = 99
            path.write_text(json.dumps(context)+'\n')
            with self.assertRaisesRegex(ValueError, 'target road'):
                audit(center, outer, decode_video=False)
