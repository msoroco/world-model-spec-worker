import importlib.util
from pathlib import Path
import unittest


module_path = Path(__file__).resolve().parents[1] / 'excavation_park.py'
spec = importlib.util.spec_from_file_location('excavation_park', module_path)
probe = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)


def scene(case):
    data = dict(cell_id='C229405', actor='motor_vehicle_driver',
                driver_present=True, motor_vehicle=True,
                highway_public_access=True, highway_dedicated=True,
                excavation_kind='highway_excavation', relation=case.relation,
                halt_activity=case.activity, passage=case.passage,
                exception=case.exception, vehicle_target_xy=[1, 2],
                traffic_start_xy=[0, 0], excavation_rect_m=[0, 0, 2, 1],
                target_body_rect_m=[0, 2, 2, 3],
                planned_passage_width_m=2.3, parking_route_xy=[[0, 3], [1, 2]],
                traffic_route_xy=[[0, 0], [20, 0]],
                conflicting_traffic_id='conflict-1', authority_record_id='order-1')
    for field in ('highway', 'vehicle', 'driver', 'excavation', 'parking_route',
                  'traffic_route', 'traffic_actor', 'halt_activity', 'exception'):
        data[field + '_source_sha256'] = 'a' * 64
    return data


def rows(case, data):
    out = []
    for i in range(900):
        row = dict(original_frame=1000+i, time_s=i/20,
                   vehicle_id='ego-1', traffic_id='traffic-1',
                   relation=case.relation, halt_activity=case.activity,
                   exception=case.exception,
                   vehicle_body_rect_m=[0, 2, 2, 3],
                   excavation_rect_m=[0, 0, 2, 1],
                   passage_width_m=2.3, traffic_speed_mps=4,
                   vehicle_speed_mps=0 if i >= 50 else 2)
        for field in ('frame', 'vehicle_motion', 'vehicle_body', 'excavation',
                      'passage', 'traffic_motion', 'activity', 'exception'):
            row[field + '_source_sha256'] = 'a' * 64
        row['excavation_source_sha256'] = data['excavation_source_sha256']
        out.append(row)
    return out


class Adapter:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def __getattr__(self, name):
        def invoke(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            if name == 'spawn_traffic' and self.fail:
                return None
            if name.startswith('spawn_'):
                return name
        return invoke


class ExcavationTests(unittest.TestCase):
    def test_all_case_constructions_and_measurements(self):
        for case in probe.CASES:
            with self.subTest(case=case.case_id):
                data = scene(case)
                adapter = Adapter()
                built = probe.construct(adapter, data, case)
                self.assertEqual(built['case_id'], case.case_id)
                self.assertIn('set_halt_route', [x[0] for x in adapter.calls])
                self.assertIn('set_exception_context', [x[0] for x in adapter.calls])
                measured = probe.measure_original(rows(case, data), data, case)
                self.assertEqual(measured['frame_count'], 900)
                self.assertEqual(measured['minimum_body_excavation_gap_m'], 1)
                self.assertIsNone(measured['legal_obstruction_judgment'])

    def test_missing_original_source_rejected(self):
        case = probe.CASES[0]
        data = scene(case)
        records = rows(case, data)
        del records[3]['passage_source_sha256']
        with self.assertRaisesRegex(ValueError, 'source missing'):
            probe.measure_original(records, data, case)

    def test_context_and_cleanup(self):
        case = probe.CASES[0]
        data = scene(case)
        del data['highway_source_sha256']
        with self.assertRaisesRegex(ValueError, 'original context'):
            probe.validate_scene(data, case)
        adapter = Adapter(fail=True)
        with self.assertRaisesRegex(ValueError, 'traffic spawn failed'):
            probe.construct(adapter, scene(case), case)
        self.assertEqual(adapter.calls[-1][0], 'destroy')


if __name__ == '__main__':
    unittest.main()
