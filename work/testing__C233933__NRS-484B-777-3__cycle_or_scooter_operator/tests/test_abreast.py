import importlib.util
from pathlib import Path
import sys
import unittest


spec = importlib.util.spec_from_file_location(
    'abreast', Path(__file__).resolve().parents[1] / 'abreast.py')
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def scene(case):
    ids = ['ego', 'control'] + (['companion'] if case.riders == 3 else [])
    s = {'cell_id': 'C233933', 'actor': 'cycle_or_scooter_operator',
         'highway': True, 'sidewalk_absent': True,
         'exclusive': case.exclusive, 'roadway': case.roadway,
         'rider_ids': ids, 'ego_id': 'ego', 'control_id': 'control',
         'vehicle_type': 'human_powered_bicycle', 'moped': False,
         'roadway_rect_m': [0., 0., 60., 10.],
         'shoulder_rect_m': [0., 9., 60., 10.],
         'occupied_surface_rect_m': [0., 0., 60., 8.],
         'rider_routes_xy': [[[0., 1. + j], [40., 1. + j]]
                             for j in range(case.riders)]}
    s.update({f + '_source_sha256': f + '-hash' for f in mod.SOURCES})
    return s


def rows(case):
    s = scene(case)
    out = []
    for i in range(900):
        r = {'original_frame': i, 'time_s': i / 20,
             'rider_ids': s['rider_ids'], 'exclusive': case.exclusive,
             'roadway': case.roadway,
             'rider_xy': [[i / 20, 1. + j] for j in range(case.riders)],
             'rider_speed_mps': [1.] * case.riders}
        r.update({f + '_source_sha256': s[f + '_source_sha256']
                  for f in mod.SOURCES})
        out.append(r)
    return out


class Adapter:
    def __init__(self, fail=False):
        self.fail = fail
        self.destroyed = []

    def spawn_bicycle(self, rider_id, xy):
        return rider_id

    def set_route(self, actor, route):
        if self.fail and actor == 'control':
            raise RuntimeError('route failed')

    def destroy(self, actor):
        self.destroyed.append(actor)


class AbreastTests(unittest.TestCase):
    def test_all_cases_construct_and_measure(self):
        for case in mod.CASES:
            with self.subTest(case=case.name):
                s = scene(case)
                self.assertEqual(len(mod.construct(Adapter(), s, case)['owned']),
                                 case.riders)
                result = mod.measure_original(rows(case), s, case)
                self.assertEqual(result['rider_count'], case.riders)
                self.assertIsNone(result['abreast_legal_judgment'])

    def test_all_sources_required(self):
        case = mod.CASES[0]
        for field in mod.SOURCES:
            s = scene(case)
            del s[field + '_source_sha256']
            with self.subTest(field=field), self.assertRaises(ValueError):
                mod.validate_scene(s, case)

    def test_moped_and_exception_substitution_rejected(self):
        case = mod.CASES[0]
        for key, value in (('moped', True), ('exclusive', True),
                           ('roadway', False), ('sidewalk_absent', False)):
            s = scene(case)
            s[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                mod.validate_scene(s, case)

    def test_original_shoulder_and_formation_change_rejected(self):
        case = mod.CASES[0]
        for position in ([8., 9.5], [12., 2.]):
            original = rows(case)
            original[160]['rider_xy'][0] = position
            with self.subTest(position=position), self.assertRaises(ValueError):
                mod.measure_original(original, scene(case), case)

    def test_failed_route_cleans_owned_bicycles(self):
        case = mod.CASES[0]
        a = Adapter(fail=True)
        with self.assertRaises(RuntimeError):
            mod.construct(a, scene(case), case)
        self.assertEqual(a.destroyed, ['control', 'ego'])

    def test_source_routes_keep_separate_riders_on_surveyed_surface(self):
        case = mod.CASES[0]
        for change in ('shoulder', 'unmatched_station'):
            s = scene(case)
            if change == 'shoulder':
                s['rider_routes_xy'][2][1] = [40., 9.5]
            else:
                s['rider_routes_xy'][2][1] = [39., 3.]
            with self.subTest(change=change), self.assertRaises(ValueError):
                mod.validate_scene(s, case)


if __name__ == '__main__':
    unittest.main()
