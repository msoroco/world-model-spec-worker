import importlib.util
from pathlib import Path
import sys
import unittest


spec = importlib.util.spec_from_file_location(
    'city_space', Path(__file__).resolve().parents[1] / 'city_space.py')
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def scene(case):
    s = {'cell_id': 'C229439', 'actor': 'vehicle_parker',
         'vehicle_id': 'v1', 'parking_person_id': 'p1',
         'city_location_kind': 'city_street',
         'city_vehicle': case.city_vehicle, 'designated': case.designated,
         'posted': case.posted, 'inside_space': case.inside_space,
         'governed_space_rect_m': [0., 0., 3., 6.],
         'vehicle_footprint_rect_m': [.2, .2, 2., 4.],
         'parking_route_xy': [[-2., -2.], [1., 1.]],
         'park_start_frame': 100,
         'official_device_text': 'City vehicles only',
         'city_vehicle_authority_ref': 'fleet record / title source',
         'council_designation_ref': 'Council designation record'}
    s.update({f + '_source_sha256': f + '-hash' for f in mod.SOURCE_FIELDS})
    return s


def rows(case):
    s = scene(case)
    out = []
    for i in range(900):
        r = {'original_frame': i, 'time_s': i / 20,
             'vehicle_id': 'v1', 'parking_person_id': 'p1',
             'official_device_text': 'City vehicles only',
             'city_vehicle': case.city_vehicle, 'designated': case.designated,
             'posted': case.posted,
             'vehicle_center_xy': [1., 1.] if case.inside_space else [8., 8.],
             'vehicle_footprint_rect_m': [.2, .2, 2., 4.] if case.inside_space
             else [7., 7., 9., 9.],
             'speed_mps': 1. if i < 100 else 0.}
        r.update({f + '_source_sha256': s[f + '_source_sha256']
                  for f in mod.SOURCE_FIELDS})
        out.append(r)
    return out


class Adapter:
    def __init__(self, fail=False):
        self.fail = fail
        self.destroyed = []
        self.commands = []

    def spawn_device(self, text, bounds):
        self.commands.append(('device', text, bounds))
        return 'device'

    def spawn_vehicle(self, position):
        self.commands.append(('vehicle', position))
        return 'vehicle'

    def set_parking_route(self, vehicle, route, frame):
        self.commands.append(('route', vehicle, frame))
        if self.fail:
            raise RuntimeError('route failed')

    def destroy(self, actor):
        self.destroyed.append(actor)


class CitySpaceTests(unittest.TestCase):
    def test_all_cases_construct_and_measure(self):
        for case in mod.CASES:
            with self.subTest(case=case.name):
                adapter = Adapter()
                self.assertEqual(mod.construct(adapter, scene(case), case)['owned'],
                                 ('device', 'vehicle'))
                result = mod.measure_original(rows(case), scene(case), case)
                self.assertEqual(result['parked_frames'], 800)
                self.assertEqual(result['all_centers_inside_governed_space'],
                                 case.inside_space)
                self.assertEqual(result['all_footprints_overlap_governed_space'],
                                 case.inside_space)
                self.assertIsNone(result['legal_judgment'])

    def test_authority_and_context_sources_required(self):
        case = mod.CASES[0]
        for field in mod.SOURCE_FIELDS:
            s = scene(case)
            del s[field + '_source_sha256']
            with self.subTest(field=field), self.assertRaises(ValueError):
                mod.validate_scene(s, case)
        for field in ('city_vehicle_authority_ref', 'council_designation_ref'):
            s = scene(case)
            del s[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                mod.validate_scene(s, case)

    def test_livery_does_not_substitute_for_authority(self):
        case = mod.CASES[0]
        s = scene(case)
        s['city_vehicle_authority_ref'] = ''
        s['city_livery'] = 'Municipal-looking paint'
        with self.assertRaisesRegex(ValueError, 'authoritative vehicle status'):
            mod.validate_scene(s, case)

    def test_source_change_and_movement_rejected(self):
        case = mod.CASES[0]
        for key, value in (('council_designation_source_sha256', 'wrong'),
                           ('speed_mps', 1.),
                           ('vehicle_footprint_rect_m', [8., 8., 9., 9.])):
            original = rows(case)
            original[200][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                mod.measure_original(original, scene(case), case)

    def test_center_outside_does_not_hide_footprint_overlap(self):
        case = mod.CASES[-1]
        original = rows(case)
        original[200]['vehicle_footprint_rect_m'] = [2.9, .2, 4., 4.]
        with self.assertRaisesRegex(ValueError, 'footprint occupancy'):
            mod.measure_original(original, scene(case), case)

    def test_failed_route_cleans_both_owned_actors(self):
        case = mod.CASES[0]
        adapter = Adapter(fail=True)
        with self.assertRaises(RuntimeError):
            mod.construct(adapter, scene(case), case)
        self.assertEqual(adapter.destroyed, ['vehicle', 'device'])


if __name__ == '__main__':
    unittest.main()
