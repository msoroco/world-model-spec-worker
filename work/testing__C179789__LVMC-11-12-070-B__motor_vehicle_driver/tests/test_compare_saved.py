"""Diagnostic protocol tests for exact original comparison audit binding."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from compare_saved import compare


class ComparisonTests(unittest.TestCase):
    def test_exact_id_and_fixed_source_checks(self):
        plan = json.loads((HERE / 'case-plan.json').read_text())
        pair = next(row for row in plan['comparisons'] if len(row['case_ids']) == 2)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            index = {}
            for position, case in enumerate(pair['case_ids']):
                report = {'format': 'c179789-original-delivery-audit-v1',
                          'case_id': case, 'frame_count': 900, 'physical_completion': True,
                          'antecedent_legal_review': 'unresolved',
                          'right_of_way_legal_review': 'unresolved',
                          'map_sha256': 'a' * 64, 'intersection_id': 'fixture-junction',
                          'entering_maneuver': 'cross', 'fixed_sources': {'road.xodr': 'a' * 64},
                          'through_request': 'yield_request' if position == 0 else 'continue_request',
                          'through_highway_measurement': {'through_preentry_min_speed_mps': 2 + position}}
                path = root / ('report-' + str(position) + '.json')
                path.write_text(json.dumps(report) + '\n')
                index[case] = str(path)
            self.assertEqual(compare(index, pair['comparison_id'])['comparison_id'], pair['comparison_id'])
            with self.assertRaisesRegex(ValueError, 'expected comparison identity missing'):
                compare(index, 'wrong-comparison')
            changed = json.loads(Path(index[pair['case_ids'][1]]).read_text())
            changed['fixed_sources'] = {'road.xodr': 'b' * 64}
            Path(index[pair['case_ids'][1]]).write_text(json.dumps(changed) + '\n')
            with self.assertRaisesRegex(ValueError, 'fixed original comparison source changed'):
                compare(index, pair['comparison_id'])


if __name__ == '__main__':
    unittest.main()
