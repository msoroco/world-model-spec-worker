import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ped_entry import CASES, construct, measure_original, validate_scene


def scene(case):
    x = {'cell_id': 'C227824', 'actor': 'pedestrian',
         'official_vehicle_signal': True, 'steady_red': True,
         'green_turn_arrow': True,
         'other_device_display': case.other_device_display,
         'pedestrian_route_xy': [[-3, 0], [-1, 0], [2, 0]],
         'start_signed_boundary_m': -2}
    for field in ('jurisdiction', 'highway_dedication', 'public_vehicle_use',
                  'highway_boundary', 'person_afoot', 'facing_orientation',
                  'official_signal', 'red_arrow_timing', 'other_device_inventory',
                  'other_device_display', 'pedestrian_route'):
        x[field + '_source_sha256'] = 'fixture-' + field
    return x


def rows(x, case):
    return [{'original_frame': 400 + i, 'time_s': i / 20,
             **{field + '_sha256': 'fixture-' + field for field in
                ('source', 'pedestrian_body', 'pedestrian_motion',
                 'highway_boundary', 'signal_display', 'other_device_display',
                 'facing_orientation')},
             'highway_boundary_source_sha256': x['highway_boundary_source_sha256'],
             'other_device_display': case.other_device_display,
             'pedestrian_id': 'walker', 'person_afoot': True,
             'facing_signal': True, 'official_steady_red': True,
             'official_green_turn_arrow': True,
             'body_nearest_signed_boundary_m': 1 if case.movement == 'enter' and i >= 120 else -2}
            for i in range(900)]


class Adapter:
    def __init__(self, fail=False):
        self.events = []
        self.fail = fail

    def spawn_pedestrian(self, xy):
        self.events.append(('spawn', tuple(xy)))
        return 'walker'

    def set_official_signal(self, steady_red, green_turn_arrow):
        self.events.append(('signal', steady_red, green_turn_arrow))

    def set_other_device(self, display):
        self.events.append(('device', display))

    def set_pedestrian_route(self, pedestrian, route, movement):
        self.events.append(('route', movement))
        if self.fail:
            raise RuntimeError('route failed')

    def destroy(self, actor):
        self.events.append(('destroy', actor))


class PedEntryTest(unittest.TestCase):
    def test_four_exact_cases(self):
        for case in CASES:
            with self.subTest(case=case.case_id):
                x = scene(case)
                self.assertIsNone(validate_scene(x, case)['pedestrian_permission_judgment'])
                adapter = Adapter()
                self.assertIsNone(construct(adapter, x, case)['legal_judgment'])
                self.assertEqual(adapter.events[-1], ('route', case.movement))
                measured = measure_original(rows(x, case), x, case)
                self.assertEqual(measured['frame_count'], 900)
                self.assertEqual(measured['first_original_entry_frame'],
                                 520 if case.movement == 'enter' else None)
                self.assertFalse(measured['vehicle_arrow_is_pedestrian_permission'])

    def test_scene_and_signal_rejection(self):
        x = scene(CASES[0]); x['green_turn_arrow'] = False
        with self.assertRaisesRegex(ValueError, 'red/green-arrow'):
            validate_scene(x, CASES[0])
        x = scene(CASES[0]); del x['other_device_inventory_source_sha256']
        with self.assertRaisesRegex(ValueError, 'original pedestrian scene source'):
            validate_scene(x, CASES[0])

    def test_original_join_and_entry_rejection(self):
        x = scene(CASES[0]); a = rows(x, CASES[0]); a[5]['pedestrian_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            measure_original(a, x, CASES[0])
        a = rows(x, CASES[0]); a[5]['signal_display_sha256'] = ''
        with self.assertRaisesRegex(ValueError, 'original source missing'):
            measure_original(a, x, CASES[0])
        a = rows(x, CASES[0]); a[120]['official_steady_red'] = False
        with self.assertRaisesRegex(ValueError, 'person/signal'):
            measure_original(a, x, CASES[0])
        a = rows(x, CASES[0]);
        for row in a: row['body_nearest_signed_boundary_m'] = -2
        with self.assertRaisesRegex(ValueError, 'entry absent'):
            measure_original(a, x, CASES[0])

    def test_owned_cleanup(self):
        adapter = Adapter(fail=True)
        with self.assertRaisesRegex(RuntimeError, 'route failed'):
            construct(adapter, scene(CASES[0]), CASES[0])
        self.assertEqual(adapter.events[-1], ('destroy', 'walker'))


if __name__ == '__main__':
    unittest.main()
