import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from turn_origin_comparison_audit import CAMERAS, PREFIX, audit
from test_turn_origin_finalizer import sources


def side(root, *, outer=False):
    sources(root)
    case = PREFIX+('left_outer_east' if outer else 'left_center_east')
    config = json.loads((root/'config.json').read_text())
    config['selected_case_id'] = case
    config['case']['case_id'] = case
    config['cameras'] = [{'name': name} for name in CAMERAS]
    (root/'config.json').write_text(json.dumps(config))
    context = json.loads((root/'case_context.json').read_text())
    context.update({'case_id': case, 'target_exit_road_id': 25,
                    'target_exit_lane_id': 1})
    (root/'case_context.json').write_text(json.dumps(context))
    if outer:
        rows = [json.loads(line) for line in (root/'turn_origin_native.jsonl').read_text().splitlines()]
        for row in rows:
            row['lane_id'] = 2
        (root/'turn_origin_native.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))


class TurnOriginComparisonAuditTests(unittest.TestCase):
    def test_distinct_origin_same_target_and_missing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            center, outer = Path(directory)/'center', Path(directory)/'outer'
            center.mkdir(); outer.mkdir()
            side(center); side(outer, outer=True)
            proof = audit(center, outer, decode_video=False)
            self.assertEqual(proof['observed_difference'],
                             {'center_origin_lane_id': 1, 'outer_origin_lane_id': 2})
            self.assertFalse(proof['legal_acceptance_claimed'])
            (outer/'turn_origin_native.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                audit(center, outer, decode_video=False)

    def test_changed_target_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            center, outer = Path(directory)/'center', Path(directory)/'outer'
            center.mkdir(); outer.mkdir()
            side(center); side(outer, outer=True)
            context = json.loads((outer/'case_context.json').read_text())
            context['target_exit_road_id'] = 99
            (outer/'case_context.json').write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, 'target or authored fixed'):
                audit(center, outer, decode_video=False)


if __name__ == '__main__':
    unittest.main()
