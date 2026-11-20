"""Westbound pair checks on original source rows."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_turn_origin_comparison_audit import side
from west_turn_origin_comparison_audit import audit


def west_side(root, *, outer=False):
    side(root, outer=outer)
    case = ('heldout__C374648__LVMC-11-12-100-C__motor_vehicle_driver__'
            + ('left_outer_west' if outer else 'left_center_west'))
    config = json.loads((root/'config.json').read_text())
    config['selected_case_id'] = case
    config['case']['case_id'] = case
    (root/'config.json').write_text(json.dumps(config))
    context = json.loads((root/'case_context.json').read_text())
    context['case_id'] = case
    context['target_exit_lane_id'] = -1
    (root/'case_context.json').write_text(json.dumps(context))
    rows = [json.loads(line) for line in
            (root/'turn_origin_native.jsonl').read_text().splitlines()]
    for row in rows:
        row['ego_forward_xy'] = [-v for v in row['ego_forward_xy']]
        row['lane_id'] = -row['lane_id']
        row['center_turn_lane_id'] = -row['center_turn_lane_id']
        row['center_marking_source_ids'] = [
            source.replace('lane:1:', 'lane:-1:')
            for source in row['center_marking_source_ids']]
    (root/'turn_origin_native.jsonl').write_text(''.join(
        json.dumps(row)+'\n' for row in rows))


class WestTurnOriginComparisonTests(unittest.TestCase):
    def test_fixed_west_target_and_distinct_origins(self):
        with tempfile.TemporaryDirectory() as directory:
            center, outer = Path(directory)/'center', Path(directory)/'outer'
            center.mkdir(); outer.mkdir()
            west_side(center); west_side(outer, outer=True)
            proof = audit(center, outer, decode_video=False)
            self.assertEqual(proof['observed_difference'],
                             {'center_origin_lane_id': -1,
                              'outer_origin_lane_id': -2})

    def test_mismatched_west_target_rejects(self):
        with tempfile.TemporaryDirectory() as directory:
            center, outer = Path(directory)/'center', Path(directory)/'outer'
            center.mkdir(); outer.mkdir()
            west_side(center); west_side(outer, outer=True)
            context = json.loads((outer/'case_context.json').read_text())
            context['target_exit_lane_id'] = 42
            (outer/'case_context.json').write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, 'target or authored fixed'):
                audit(center, outer, decode_video=False)
