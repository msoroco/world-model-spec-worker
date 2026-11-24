import importlib.util
from pathlib import Path
import sys
import unittest


spec = importlib.util.spec_from_file_location(
    'contest_aid', Path(__file__).resolve().parents[1] / 'contest_aid.py')
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def scene(case):
    s = {'cell_id': 'C229628', 'actor': 'motor_vehicle_driver',
         'municipal_jurisdiction': True, 'highway': case.highway,
         'candidate_contest': case.candidate_contest, 'cue': case.cue,
         'ego_person_id': 'p1', 'other_person_id': 'p2',
         'ego_vehicle_id': 'v1', 'other_vehicle_id': 'v2',
         'ego_route_xy': [[0., 0.], [10., 0.]],
         'other_route_xy': [[0., 3.], [10., 3.]],
         'lane_marking_xy': [[0., 1.5], [10., 1.5]],
         'cue_frame': 100, 'other_start_frame': 120}
    s.update({f + '_source_sha256': f + '-hash' for f in mod.SOURCE_FIELDS})
    return s


def rows(case):
    s = scene(case)
    out = []
    for i in range(900):
        r = {'original_frame': i, 'time_s': i / 20,
             'highway': case.highway,
             'candidate_contest': case.candidate_contest,
             'cue_observed': case.cue and i == 100,
             'ego_speed_mps': 1.,
             'other_speed_mps': 1. if i >= 120 else 0.,
             'ego_accel_mps2': 0., 'other_accel_mps2': 0.,
             'ego_xy': [i / 20, 0.], 'other_xy': [i / 20, 3.]}
        r.update({n: s[n] for n in ('ego_person_id', 'other_person_id',
                                    'ego_vehicle_id', 'other_vehicle_id')})
        r.update({f + '_source_sha256': s[f + '_source_sha256']
                  for f in mod.SOURCE_FIELDS})
        out.append(r)
    return out


class Adapter:
    def __init__(self, fail=False):
        self.fail = fail
        self.spawned = []
        self.destroyed = []

    def spawn_vehicle(self, position):
        actor = 'v' + str(len(self.spawned) + 1)
        self.spawned.append(actor)
        return actor

    def set_route(self, actor, route):
        pass

    def set_start_cue(self, actor, frame, cue):
        if self.fail:
            raise RuntimeError('cue failed')

    def set_other_start(self, actor, frame, contest):
        pass

    def destroy(self, actor):
        self.destroyed.append(actor)


class ContestAidTests(unittest.TestCase):
    def test_all_cases_construct_and_measure(self):
        for case in mod.CASES:
            with self.subTest(case=case.name):
                a = Adapter()
                self.assertEqual(mod.construct(a, scene(case), case)['owned'],
                                 ('v1', 'v2'))
                result = mod.measure_original(rows(case), scene(case), case)
                self.assertEqual(result['cue_frame'], 100 if case.cue else None)
                self.assertEqual(result['other_motion_first_frame'], 120)
                self.assertIsNone(result['aid_abet_judgment'])

    def test_all_distinct_sources_required(self):
        case = mod.CASES[0]
        for field in mod.SOURCE_FIELDS:
            s = scene(case)
            del s[field + '_source_sha256']
            with self.subTest(field=field), self.assertRaises(ValueError):
                mod.validate_scene(s, case)

    def test_case_and_original_cue_change_rejected(self):
        case = mod.CASES[0]
        s = scene(case)
        s['highway'] = False
        with self.assertRaises(ValueError):
            mod.validate_scene(s, case)
        original = rows(case)
        original[100]['cue_observed'] = False
        with self.assertRaisesRegex(ValueError, 'cue realization'):
            mod.measure_original(original, scene(case), case)

    def test_source_context_change_rejected(self):
        case = mod.CASES[0]
        original = rows(case)
        original[200]['contest_episode_source_sha256'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'original source changed'):
            mod.measure_original(original, scene(case), case)

    def test_failed_cue_cleans_both_vehicles(self):
        case = mod.CASES[0]
        a = Adapter(fail=True)
        with self.assertRaises(RuntimeError):
            mod.construct(a, scene(case), case)
        self.assertEqual(a.destroyed, ['v2', 'v1'])


if __name__ == '__main__':
    unittest.main()
