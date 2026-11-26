"""CPU checks for exact curb/hour construction contrast and source rejection."""
import copy
import json
from pathlib import Path
import unittest

from yellow_plan import check, measure_requested

PACKAGE = Path(__file__).resolve().parent.parent


def file_content(construction, path):
    return next(item['content'] for item in construction['files'] if item['path'] == path)


class DraftComparison(unittest.TestCase):
    def test_both_cases_and_controlled_hour(self):
        cases = []
        for suffix, active in (('probe_a', 600), ('probe_b', 0)):
            construction = json.loads((PACKAGE / 'native-draft' / suffix / 'construction.json').read_text())
            config = json.loads(file_content(construction, 'config.json'))
            road = file_content(construction, 'yellow-road.xodr')
            rows = [json.loads(line) for line in file_content(construction, 'requested-track.jsonl').splitlines()]
            self.assertEqual(check(config, road)['frames'], 600)
            self.assertEqual(measure_requested(rows, config)['sign_active_request_frames'], active)
            cases.append((config, road, rows))
        (a, road_a, rows_a), (b, road_b, rows_b) = cases
        self.assertEqual(road_a, road_b)
        self.assertEqual(a['cameras'], b['cameras'])
        self.assertEqual(a['taxi_blueprint_filter'], b['taxi_blueprint_filter'])
        self.assertEqual(a['requested_purpose'], b['requested_purpose'])
        self.assertEqual([r['requested_stop_xy_m'] for r in rows_a],
                         [r['requested_stop_xy_m'] for r in rows_b])
        self.assertEqual([r['requested_speed_mps'] for r in rows_a],
                         [r['requested_speed_mps'] for r in rows_b])
        wrong = copy.deepcopy(rows_a)
        wrong.pop()
        with self.assertRaisesRegex(ValueError, '600-frame'):
            measure_requested(wrong, a)
        wrong = copy.deepcopy(rows_a)
        wrong[100]['civil_time_local'] = rows_b[100]['civil_time_local']
        with self.assertRaisesRegex(ValueError, 'Civil time join'):
            measure_requested(wrong, a)
        with self.assertRaisesRegex(ValueError, 'Yellow parking'):
            check(a, road_a.replace('color="yellow"', 'color="white"'))


if __name__ == '__main__':
    unittest.main()
