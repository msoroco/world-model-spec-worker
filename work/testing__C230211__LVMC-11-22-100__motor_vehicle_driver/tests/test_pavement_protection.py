import importlib.util
from pathlib import Path
import sys
import unittest


path = Path(__file__).resolve().parents[1] / 'pavement_protection.py'
spec = importlib.util.spec_from_file_location('pavement_protection', path)
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)


def scene(case):
    s = dict(cell_id='C230211', actor='motor_vehicle_driver',
             person_is_driver=True, vehicle_qualifies=True,
             municipal_jurisdiction=True, pavement_condition='newly_laid',
             pavement_rect_m=[0, 0, 10, 4], pavement_id='p1',
             protection=case.protection, route_kind=case.route,
             employee_engaged=case.employee_engaged,
             employee_pavement_id='p1', work_kind='paving', work_active=True,
             barrier_rect_m=[-1, 0, 0, 4], warning_person_id='w1',
             barrier_perimeter_rects_m=[[-1, -1, 0, 5], [10, -1, 11, 5],
                                        [0, -1, 10, 0], [0, 4, 10, 5]],
             warning_person_xy=[-1, 2], sign_xy=[-1, 2],
             sign_text=('highway_closed' if case.protection ==
                        'highway_closed_sign' else 'do_not_drive_on_pavement'),
             vehicle_route_xy=[[-5, 2], [5, 2], [15, 2]] if case.route == 'cross'
             else [[-5, 6], [5, 6], [15, 6]])
    for field in ('jurisdiction', 'driver', 'vehicle', 'pavement_condition',
                  'pavement_extent', 'protection_geometry',
                  'protection_placement_time', 'vehicle_route',
                  'employment', 'work_activity'):
        s[field + '_source_sha256'] = 'a' * 64
    return s


def rows(case, s):
    output = []
    for i in range(900):
        x = -5 if i < 100 else 5 if i < 500 else 15
        y = 2 if case.route == 'cross' else 6
        row = dict(original_frame=100+i, time_s=i/20,
                   vehicle_id='ego', vehicle_position_xy=[x, y],
                   protection=case.protection,
                   employee_engaged=case.employee_engaged)
        for field in ('frame', 'vehicle_motion', 'pavement_condition',
                      'pavement_extent', 'protection_geometry',
                      'protection_placement_time', 'employment', 'work_activity'):
            row[field + '_source_sha256'] = 'a' * 64
        row['pavement_extent_source_sha256'] = s['pavement_extent_source_sha256']
        output.append(row)
    return output


class Adapter:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def __getattr__(self, name):
        def invoke(*args):
            self.calls.append((name, args))
            if name.startswith('spawn_') or name.startswith('place_'):
                return None if self.fail and name == 'spawn_vehicle' else name
        return invoke


class PavementTests(unittest.TestCase):
    def test_all_cases_construct_and_measure(self):
        for case in probe.CASES:
            with self.subTest(case=case.name):
                s = scene(case)
                adapter = Adapter()
                probe.construct(adapter, s, case)
                self.assertIn('set_vehicle_route', [x[0] for x in adapter.calls])
                result = probe.measure_original(rows(case, s), s, case)
                self.assertEqual(result['entered_protected_pavement'],
                                 case.route == 'cross')
                self.assertIsNone(result['legal_judgment'])

    def test_missing_source_and_crossing_rejected(self):
        case = probe.CASES[0]
        s = scene(case)
        data = rows(case, s)
        del data[2]['protection_geometry_source_sha256']
        with self.assertRaisesRegex(ValueError, 'source missing'):
            probe.measure_original(data, s, case)
        data = rows(case, s)
        for row in data:
            row['vehicle_position_xy'] = [-5, 6]
        with self.assertRaisesRegex(ValueError, 'crossing missing'):
            probe.measure_original(data, s, case)

    def test_employee_and_spawn_failure(self):
        case = probe.CASES[-1]
        s = scene(case)
        s['employee_pavement_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'same-pavement'):
            probe.validate_scene(s, case)
        with self.assertRaisesRegex(ValueError, 'vehicle spawn failed'):
            probe.construct(Adapter(fail=True), scene(case), case)


if __name__ == '__main__':
    unittest.main()
