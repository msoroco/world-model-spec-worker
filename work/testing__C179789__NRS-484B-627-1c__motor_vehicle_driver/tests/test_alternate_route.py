import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alternate_route import CASES, construct, measure_original, validate_scene


def scene(case):
    x = {'cell_id': 'C179789', 'actor': 'motor_vehicle_driver',
         'controlled_access': case.controlled_access,
         'alternate_declared': case.alternate_declared,
         'alternate_restriction_state': 'open' if case.alternate_declared else 'restricted',
         'main_route_xy': [[0, 0], [10, 0], [30, 0]],
         'alternate_route_xy': [[0, 0], [10, 0], [20, 10]],
         'follower_route_xy': [[0, 0], [10, 0], [30, 0]]}
    for field in ('jurisdiction', 'highway_classification', 'controlled_access_classification',
                  'ego_vehicle', 'ego_driver_control', 'main_route', 'alternate_route',
                  'alternate_restrictions', 'journey_destination', 'follower_route',
                  'follower_driver', 'shared_segment', 'following_motion'):
        x[field + '_source_sha256'] = 'fixture-' + field
    return x


def rows(x, case):
    return [{'original_frame': 700 + i, 'time_s': i / 20,
             **{field + '_sha256': 'fixture-' + field for field in
                ('source', 'ego_motion', 'follower_motion', 'route_observation',
                 'map_classification', 'journey_context', 'shared_segment')},
             'shared_segment_source_sha256': x['shared_segment_source_sha256'],
             'controlled_access': case.controlled_access,
             'alternate_restriction_state': x['alternate_restriction_state'],
             'ego_id': 'ego', 'follower_id': 'follower',
             'following_gap_m': 8, 'ego_speed_mps': 3,
             'follower_speed_mps': 5, 'ego_route_station_m': i / 10,
             'follower_route_station_m': i / 10 - 8,
             'actual_route_choice': case.route_choice}
            for i in range(900)]


class Adapter:
    def __init__(self, fail=False):
        self.events = []
        self.fail = fail

    def spawn_vehicle(self, position, role):
        self.events.append(('spawn', role))
        return role

    def set_route(self, actor, route):
        self.events.append(('route', actor, tuple(map(tuple, route))))
        if self.fail:
            raise RuntimeError('route failed')

    def set_following_context(self, follower, ego, segment):
        self.events.append(('following', follower, ego))

    def destroy(self, actor):
        self.events.append(('destroy', actor))


class AlternateRouteTest(unittest.TestCase):
    def test_four_exact_cases(self):
        for case in CASES:
            with self.subTest(case=case.case_id):
                x = scene(case)
                self.assertIsNone(validate_scene(x, case)['legal_judgment'])
                self.assertIsNone(construct(Adapter(), x, case)['legal_judgment'])
                out = measure_original(rows(x, case), x, case)
                self.assertEqual(out['frame_count'], 900)
                self.assertEqual(out['terminal_actual_route'], case.route_choice)
                self.assertIsNone(out['possible_route_judgment'])

    def test_route_source_and_restriction_rejection(self):
        x = scene(CASES[0]); x['alternate_route_xy'] = x['main_route_xy']
        with self.assertRaisesRegex(ValueError, 'does not differ'):
            validate_scene(x, CASES[0])
        x = scene(CASES[0]); del x['alternate_restrictions_source_sha256']
        with self.assertRaisesRegex(ValueError, 'original journey source'):
            validate_scene(x, CASES[0])
        x = scene(CASES[0]); x['alternate_restriction_state'] = 'restricted'
        with self.assertRaisesRegex(ValueError, 'declaration/restriction'):
            validate_scene(x, CASES[0])

    def test_original_identity_and_route_rejection(self):
        x = scene(CASES[0]); a = rows(x, CASES[0]); a[5]['follower_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            measure_original(a, x, CASES[0])
        a = rows(x, CASES[0]); a[5]['map_classification_sha256'] = ''
        with self.assertRaisesRegex(ValueError, 'original source missing'):
            measure_original(a, x, CASES[0])
        a = rows(x, CASES[0]); a[-1]['actual_route_choice'] = 'main'
        with self.assertRaisesRegex(ValueError, 'terminal route differs'):
            measure_original(a, x, CASES[0])

    def test_owned_cleanup(self):
        adapter = Adapter(fail=True)
        with self.assertRaisesRegex(RuntimeError, 'route failed'):
            construct(adapter, scene(CASES[0]), CASES[0])
        self.assertEqual(adapter.events[-2:], [('destroy', 'follower'), ('destroy', 'ego')])


if __name__ == '__main__':
    unittest.main()
