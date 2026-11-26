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

    def test_three_passenger_purposes_within_hours(self):
        configs = []
        roads = []
        for suffix, purpose in (('probe_a', 'waiting_for_passengers'),
                                ('probe_c', 'loading_passengers'),
                                ('probe_d', 'unloading_passengers')):
            construction = json.loads((PACKAGE / 'native-draft' / suffix / 'construction.json').read_text())
            config = json.loads(file_content(construction, 'config.json'))
            road = file_content(construction, 'yellow-road.xodr')
            rows = [json.loads(line) for line in file_content(construction, 'requested-track.jsonl').splitlines()]
            self.assertEqual(config['requested_purpose'], purpose)
            self.assertEqual(measure_requested(rows, config)['sign_active_request_frames'], 600)
            configs.append(config)
            roads.append(road)
        self.assertEqual(len(set(roads)), 1)
        self.assertEqual(len({json.dumps(c['cameras'], sort_keys=True) for c in configs}), 1)
        self.assertEqual({c['civil_start_local'] for c in configs}, {'2026-11-26T10:00:00'})
        wrong = {**configs[1], 'requested_purpose': 'waiting_for_passengers'}
        with self.assertRaisesRegex(ValueError, 'purpose request'):
            check(wrong, roads[1])


if __name__ == '__main__':
    unittest.main()
