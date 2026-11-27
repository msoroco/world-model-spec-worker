"""Exercise source gating, Native construction calls and original measurements."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from motorcade_spacing import CASES, execute_case, measure_original_frames, planned_spawn
from runner import check


def packet(case):
    vehicle = lambda length: {'blueprint_id': 'vehicle.synthetic',
                              'native_vehicle_class': 'motor_vehicle',
                              'body_length_m': length}
    assets = {'front': vehicle(4.8), 'ego': vehicle(4.8),
              'rear': vehicle(4.8), 'entrant': vehicle(5.9)}
    if case.towing:
        assets['group_towed_vehicle'] = {'body_length_m': 4.0}
    if case.combination_entrant:
        assets['entrant_towed_vehicle'] = {'body_length_m': 4.0}
    return {'case_suffix': case.suffix,
            'route': {'native_road_id': 1, 'directed_driving_lane_id': -1,
                      'entrant_adjacent_lane_id': -2, 'surveyed_length_m': 700,
                      'public_highway_review': 'explicit external assumption',
                      'outside_business_district_review': 'explicit external assumption'},
            'membership': {'group_kind': case.group_kind, 'reviewer': 'synthetic test',
                           'coordination_source': 'test roster',
                           'ordered_roles': ['front', 'ego', 'rear'],
                           'driver_relationships': 'separate drivers',
                           'group_purpose': 'organized shared journey'},
            'assets': assets,
            'camera_survey': [{'name': name, 'native_pose': [1, 2, 3],
                               'reviewer': 'synthetic test'}
                              for name in ('overview', 'approach',
                                           'reference_corner', 'driver_reference')]}


class Adapter:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
        return call


class ConstructionTest(unittest.TestCase):
    def test_exact_case_inventory(self):
        self.assertEqual(len(CASES), 10)
        self.assertIn(check(), {'testing__C160013__NRS-484B-127-3__motor_vehicle_driver__' + case.suffix for case in CASES})

    def test_all_alternatives_construct_native_actors(self):
        for case in CASES:
            with self.subTest(case=case.suffix):
                source = packet(case)
                station = planned_spawn(source, case)
                self.assertAlmostEqual(station['front'] - station['ego'] - 4.8,
                                       case.gap_target_m + (2 if case.towing else 0))
                adapter = Adapter()
                execute_case(adapter, source, case)
                names = [item[0] for item in adapter.calls]
                self.assertEqual(names.count('spawn_group_vehicle'), 3)
                self.assertIn('spawn_entrant', names)
                self.assertIn('schedule_entrant_entry', names)
                self.assertEqual(names.count('attach_towed_vehicle'),
                                 int(case.towing) + int(case.combination_entrant))
                self.assertIn('capture_original', names)

    def test_missing_membership_and_route_sources_rejected(self):
        case = CASES[0]
        source = packet(case)
        source['membership']['coordination_source'] = ''
        with self.assertRaisesRegex(ValueError, 'membership'):
            planned_spawn(source, case)
        source = packet(case)
        source['route']['outside_business_district_review'] = ''
        with self.assertRaisesRegex(ValueError, 'district'):
            planned_spawn(source, case)

    def test_original_body_gap_and_frame_join(self):
        case = CASES[0]
        def body(center, lane):
            return {'route_station_vertices_m': [center - 2.4] * 4 + [center + 2.4] * 4,
                    'native_lane_id': lane}
        frames = [
            {'frame': index, 'time_s': index / 20,
             'bodies': {'front': body(100, -1), 'ego': body(77.2, -1),
                        'rear': body(54.4, -1), 'entrant': body(60, -2)},
             'group_role_ids': {'front': 1, 'ego': 2, 'rear': 3},
             'controls': {}}
            for index in range(600)
        ]
        measured = measure_original_frames(frames, case)
        self.assertAlmostEqual(measured['steady_front_mean_m'], 18.0)
        self.assertAlmostEqual(measured['steady_rear_mean_m'], 18.0)
        self.assertIsNone(measured['without_danger'])
        frames[160]['bodies']['entrant'].pop('route_station_vertices_m')
        with self.assertRaisesRegex(ValueError, 'eight Native body vertices'):
            measure_original_frames(frames, case)


if __name__ == '__main__':
    unittest.main()
