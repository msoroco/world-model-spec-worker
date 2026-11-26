import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rear_signal import CASES, construct, measure_original, validate_scene


def scene(case):
    x = {'cell_id': 'C150640', 'actor': 'motor_vehicle_driver',
         'route_xy': [[-20, 0], [-5, 0], [0, 0]],
         'stop_footprint_xy': [[0, -1], [4, -1], [4, 1], [0, 1]],
         'signal_light_name': 'RightBlinker',
         'rear_vehicle': {'driver_present': case.rear_driver,
                          'longitudinal_gap_m': 8, 'lateral_offset_m': .2,
                          'spawn_xy': [-8, .2]}}
    for key in ('jurisdiction', 'one_way_route', 'stop_footprint', 'ego_vehicle',
                'ego_driver_control', 'signal_device', 'rear_visibility',
                'conflict_context', 'official_direction_context'):
        x[key + '_source_sha256'] = 'fixture-' + key
    for key in ('vehicle', 'driver', 'position', 'motion'):
        x['rear_vehicle'][key + '_source_sha256'] = 'fixture-rear-' + key
    return x


def rows(x, case):
    onset = 100 if case.signal_policy == 'before' else 300
    event = 200
    return [{'original_frame': 1000 + i, 'time_s': i / 20,
             'source_sha256': 'fixture-original',
             'ego_motion_source_sha256': 'fixture-ego-motion',
             'rear_motion_source_sha256': 'fixture-rear-motion',
             'signal_source_sha256': 'fixture-signal',
             'rear_visibility_source_sha256': 'fixture-visibility',
             'context_source_sha256': 'fixture-context',
             'route_source_sha256': x['one_way_route_source_sha256'],
             'ego_driver_in_control': True, 'rear_driver_present': case.rear_driver,
             'ego_id': 'ego', 'rear_id': 'rear',
             'rear_longitudinal_gap_m': 8, 'rear_lateral_offset_m': .2,
             'ego_speed_mps': 8 if i < event else (0 if case.maneuver == 'stop' else 4),
             'rear_speed_mps': 8, 'signal_displayed': i >= onset,
             'signal_visible_from_rear': i >= onset,
             'event_marker': case.maneuver if i == event else None}
            for i in range(900)]


class Adapter:
    def __init__(self, fail=False):
        self.events = []
        self.fail = fail

    def spawn_vehicle(self, position, role):
        self.events.append(('spawn', role))
        return role

    def set_route_and_stop(self, ego, route, footprint, maneuver):
        self.events.append(('route', maneuver))
        if self.fail:
            raise RuntimeError('route failed')

    def set_rear_driver(self, rear, present):
        self.events.append(('driver', present))

    def set_signal_policy(self, ego, policy):
        self.events.append(('signal', policy))

    def destroy(self, actor):
        self.events.append(('destroy', actor))


class RearSignalTest(unittest.TestCase):
    def test_five_exact_cases(self):
        for case in CASES:
            with self.subTest(case=case.case_id):
                x = scene(case)
                self.assertIsNone(validate_scene(x)['immediately_to_rear_judgment'])
                adapter = Adapter()
                self.assertIsNone(construct(adapter, x, case)['legal_judgment'])
                self.assertEqual(adapter.events[-1], ('signal', case.signal_policy))
                result = measure_original(rows(x, case), x, case)
                self.assertEqual(result['frame_count'], 900)
                self.assertEqual(result['signal_precedes_event'], case.signal_policy == 'before')
                self.assertIsNone(result['signal_appropriateness_judgment'])

    def test_source_and_rear_driver_rejections(self):
        x = scene(CASES[0])
        del x['rear_visibility_source_sha256']
        with self.assertRaisesRegex(ValueError, 'original scene source'):
            validate_scene(x)
        x = scene(CASES[0])
        x['rear_vehicle']['driver_present'] = False
        with self.assertRaisesRegex(ValueError, 'rear driver condition'):
            construct(Adapter(), x, CASES[0])

    def test_original_rejections(self):
        x = scene(CASES[0])
        rowset = rows(x, CASES[0])
        rowset[5]['rear_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            measure_original(rowset, x, CASES[0])
        rowset = rows(x, CASES[0])
        rowset[5]['source_sha256'] = ''
        with self.assertRaisesRegex(ValueError, 'original source missing'):
            measure_original(rowset, x, CASES[0])
        rowset = rows(x, CASES[0])
        rowset[0]['event_marker'] = 'stop'
        with self.assertRaisesRegex(ValueError, 'one original maneuver onset'):
            measure_original(rowset, x, CASES[0])
        rowset = rows(x, CASES[0])
        for row in rowset:
            row['signal_displayed'] = False
        with self.assertRaisesRegex(ValueError, 'displayed signal absent'):
            measure_original(rowset, x, CASES[0])

    def test_owned_actor_cleanup(self):
        adapter = Adapter(fail=True)
        with self.assertRaisesRegex(RuntimeError, 'route failed'):
            construct(adapter, scene(CASES[0]), CASES[0])
        self.assertEqual(adapter.events[-2:], [('destroy', 'rear'), ('destroy', 'ego')])


if __name__ == '__main__':
    unittest.main()
