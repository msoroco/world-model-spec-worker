import importlib.util
from pathlib import Path
import sys
import unittest


path = Path(__file__).resolve().parents[1] / 'inoperative_signal.py'
spec = importlib.util.spec_from_file_location('inoperative_signal', path)
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)


def scene(case):
    s = dict(cell_id='C24811', actor='motor_vehicle_driver',
             driver_controls_vehicle=True, ordinary_motor_vehicle=True,
             stop_basis=case.stop_basis, other_state=case.other_state,
             ego_policy=case.ego_policy, signal_installed=True,
             vehicular_heads_uncovered=True, official_device=True,
             governs_entrance=True, all_heads_wholly_inoperative=True,
             stop_station_m=0, entry_station_m=5,
             entrance_ids=['north', 'south', 'east', 'west'],
             marked_stop_line=case.stop_basis == 'stop_line',
             near_crosswalk=case.stop_basis == 'crosswalk',
             approach_viewpoint=case.stop_basis == 'viewpoint',
             other_vehicle_id='other', occluder_geometry=[0, 0, 2, 4],
             occluder_governs_approach=True,
             ego_route_xy=[[-10, 0], [10, 0]],
             other_route_xy=[[0, -10], [0, 10]])
    for field in ('jurisdiction', 'intersection_bounds', 'entrances',
                  'official_signal', 'signal_governance', 'signal_state',
                  'stop_line', 'crosswalk', 'viewpoint', 'occluder',
                  'ego_route', 'other_route', 'driver_control'):
        s[field + '_source_sha256'] = 'a' * 64
    return s


def rows(case, s):
    output = []
    for i in range(900):
        row = dict(original_frame=100+i, time_s=i/20,
                   ego_id='ego', other_id='other',
                   ego_station_m=-5 if i < 100 else 0 if i < 200 else 6,
                   ego_speed_mps=0 if 100 <= i < 200 else 3,
                   other_stopped=case.other_state == 'prior_stop' and
                   120 <= i < 180,
                   other_inside_intersection=case.other_state == 'inside' and
                   200 <= i < 300,
                   all_heads_wholly_inoperative=True,
                   signal_state_source_sha256=s['signal_state_source_sha256'])
        for field in ('frame', 'ego_motion', 'other_motion',
                      'intersection_bounds', 'signal_state', 'stop_geometry',
                      'occluder', 'driver_viewpoint'):
            row[field + '_source_sha256'] = 'a' * 64
        output.append(row)
    return output


class Adapter:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail
        self.spawn_count = 0

    def __getattr__(self, name):
        def invoke(*args):
            self.calls.append((name, args))
            if name == 'spawn_vehicle':
                self.spawn_count += 1
                return None if self.fail and self.spawn_count == 2 else str(self.spawn_count)
        return invoke


class SignalTests(unittest.TestCase):
    def test_all_cases_construct_and_measure(self):
        for case in probe.CASES:
            with self.subTest(case=case.name):
                s = scene(case)
                adapter = Adapter()
                probe.construct(adapter, s, case)
                self.assertIn('place_occluder', [x[0] for x in adapter.calls])
                result = probe.measure_original(rows(case, s), s, case)
                self.assertLess(result['stop_frame'], result['entry_frame'])
                self.assertIsNone(result['yield_judgment'])

    def test_partial_signal_and_source_rejected(self):
        case = probe.CASES[0]
        s = scene(case)
        s['all_heads_wholly_inoperative'] = False
        with self.assertRaisesRegex(ValueError, 'wholly inoperative'):
            probe.validate_scene(s, case)
        s = scene(case);data = rows(case, s)
        del data[2]['ego_motion_source_sha256']
        with self.assertRaisesRegex(ValueError, 'source missing'):
            probe.measure_original(data, s, case)

    def test_missing_stop_and_cleanup(self):
        case = probe.CASES[0]
        s = scene(case);data = rows(case, s)
        for row in data:
            row['ego_speed_mps'] = 3
        with self.assertRaisesRegex(ValueError, 'pre-entry stop'):
            probe.measure_original(data, s, case)
        adapter = Adapter(fail=True)
        with self.assertRaisesRegex(ValueError, 'other spawn failed'):
            probe.construct(adapter, s, case)
        self.assertEqual(adapter.calls[-1][0], 'destroy')


if __name__ == '__main__':
    unittest.main()
