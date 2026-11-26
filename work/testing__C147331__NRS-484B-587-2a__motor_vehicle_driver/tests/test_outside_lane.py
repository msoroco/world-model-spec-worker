import importlib.util
from pathlib import Path
import sys
import unittest

p = Path(__file__).resolve().parents[1] / 'outside_lane.py'
spec = importlib.util.spec_from_file_location('outside_lane_c147331', p)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class Adapter:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail
    def spawn_vehicle(self, point, **kwargs):
        self.calls.append(('spawn', point, kwargs))
        return 'ego'
    def set_route(self, actor, route, **kwargs):
        self.calls.append(('route', list(route)))
        if self.fail:
            raise RuntimeError('route failed')
    def set_capture_metadata(self, actor, metadata):
        self.calls.append(('metadata', metadata))
    def destroy(self, actor):
        self.calls.append(('destroy', actor))


def site(case):
    keys = ('traffic_left', 'traffic_right', 'entrance', 'exit', 'shoulder', 'outside')
    sign = 1 if case.approach == 'north' else -1
    lanes = {key: {'id': key, 'source_sha256': 'lanehash', 'classification': key,
                   'route': [[i, k], [i, k+20*sign]]} for k, (i, key) in enumerate(zip(range(6), keys))}
    return {'cell_id': 'C147331', 'layout': 'one_way_multilane',
            'legal_controlled_access_source_sha256': 'designation',
            'public_highway_boundary_source_sha256': 'boundary',
            'map_sha256': 'map', 'lane_marking_source_sha256': 'markings',
            'direction_of_travel': 'one_way', 'direction_source_sha256': 'direction',
            'approach_vector': [0, sign], 'lanes': lanes,
            'shoulder_paved_source_sha256': 'paved', 'sign_source_sha256': 'sign',
            'vehicle_class_source_sha256': 'vehicle', 'emergency_record_source_sha256': 'emergency',
            'subsection3_authorization_source_sha256': 'authorization',
            'approach': case.approach, 'vehicle_class': case.vehicle_class,
            'sign_permits_shoulder': case.sign_permits_shoulder,
            'emergency_required': case.emergency_required,
            'subsection3_authorized': case.subsection3_authorized}


def rows(case, n=2):
    base = {'case': case.name, 'ego_id': 'e', 'map_sha256': 'map',
            'lane_marking_source_sha256': 'markings',
            'legal_controlled_access_source_sha256': 'designation',
            'public_highway_boundary_source_sha256': 'boundary',
            'camera_plan_sha256': 'camera', 'vehicle_class': case.vehicle_class,
            'direction_source_sha256': 'direction',
            'approach': case.approach, 'sign_source_sha256': 'sign',
            'emergency_record_source_sha256': 'emergency',
            'subsection3_authorization_source_sha256': 'authorization',
            'route_class': case.route_class, 'sign_permits_shoulder': case.sign_permits_shoulder,
            'emergency_required': case.emergency_required,
            'subsection3_authorized': case.subsection3_authorized,
            'source_sha256': 'source', 'ego_lateral_m': 3.0,
            'ego_speed_mps': 8.0, 'left_marking_lateral_m': 0.0,
            'right_marking_lateral_m': 2.5, 'shoulder_outer_lateral_m': 6.0}
    return [dict(base, original_frame=100+i) for i in range(n)]


class Tests(unittest.TestCase):
    def test_routes_use_distinct_sourced_lanes(self):
        for case in m.CASES:
            with self.subTest(case=case.name):
                adapter = Adapter()
                result = m.build_case(adapter, site(case), case)
                self.assertEqual(result['route_id'], m.route_key(case))
                self.assertEqual(adapter.calls[1][1], site(case)['lanes'][m.route_key(case)]['route'])
    def test_site_and_exception_source_fail_closed(self):
        c = m.CASES[5]
        s = site(c); s['legal_controlled_access_source_sha256'] = ''
        with self.assertRaisesRegex(ValueError, 'designation source missing'):
            m.build_case(Adapter(), s, c)
        s = site(c); s['sign_permits_shoulder'] = False
        with self.assertRaisesRegex(ValueError, 'signed shoulder condition'):
            m.build_case(Adapter(), s, c)
        s = site(m.CASES[2]); s['lanes']['outside']['route'].reverse()
        with self.assertRaisesRegex(ValueError, 'route opposes sourced approach'):
            m.build_case(Adapter(), s, m.CASES[2])
    def test_cleanup_on_failed_route(self):
        a = Adapter(fail=True)
        with self.assertRaisesRegex(RuntimeError, 'route failed'):
            m.build_case(a, site(m.CASES[0]), m.CASES[0])
        self.assertEqual(a.calls[-1], ('destroy', 'ego'))
    def test_original_measurement_and_rejections(self):
        c = m.CASES[1]
        data = m.measure_original(rows(c), c)
        self.assertEqual(data['samples'][0]['ego_lateral_m'], 3.0)
        self.assertIsNone(data['legal_judgment'])
        broken = rows(c); broken[1]['original_frame'] = 120
        with self.assertRaisesRegex(ValueError, 'discontinuity'):
            m.measure_original(broken, c)
        broken = rows(c); broken[1]['sign_permits_shoulder'] = True
        with self.assertRaisesRegex(ValueError, 'sign condition'):
            m.measure_original(broken, c)
    def test_comparison_fixed_and_deliberate_difference(self):
        a = m.measure_original(rows(m.CASES[0], 900), m.CASES[0])
        b = m.measure_original(rows(m.CASES[1], 900), m.CASES[1])
        a['original_history_sha256'] = 'a'; b['original_history_sha256'] = 'b'
        self.assertEqual(m.audit_comparison(a, b, {'route_class'})['changed'], ['route_class'])
        b['fixed']['map_sha256'] = 'different'
        with self.assertRaisesRegex(ValueError, 'fixed source changed'):
            m.audit_comparison(a, b, {'route_class'})
        b['fixed']['map_sha256'] = 'map'; b['original_history_sha256'] = ''
        with self.assertRaisesRegex(ValueError, 'original source missing'):
            m.audit_comparison(a, b, {'route_class'})


if __name__ == '__main__':
    unittest.main()
