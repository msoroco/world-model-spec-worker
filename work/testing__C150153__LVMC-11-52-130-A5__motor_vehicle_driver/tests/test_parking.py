import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'parking.py'
spec = importlib.util.spec_from_file_location('parking_c150153', MODULE)
p = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = p
spec.loader.exec_module(p)


class Adapter:
    def __init__(self, bad_readback=False):
        self.calls = []
        self.bad_readback = bad_readback

    def spawn_fixture(self, *args, **kwargs):
        self.calls.append(('fixture', kwargs))
        return 'fixture'

    def lookup_fixture(self, *args):
        self.calls.append(('lookup', args))
        return 'fixture'

    def read_fixture(self, fixture):
        self.calls.append(('readback', fixture))
        return {'identity_sha256': 'fi', 'geometry_sha256': 'wrong' if self.bad_readback else 'fg',
                'physically_present': True}

    def spawn_vehicle(self, *args, **kwargs):
        self.calls.append(('vehicle', kwargs))
        return 'ego'

    def set_route(self, *args, **kwargs):
        self.calls.append(('route', kwargs))

    def set_curb_target(self, *args, **kwargs):
        self.calls.append(('curb', args, kwargs))

    def set_exception_source(self, *args):
        self.calls.append(('exception', args))

    def destroy(self, actor):
        self.calls.append(('destroy', actor))


def site():
    return {'cell_id': 'C150153', 'layout': 'one_way_road', 'map_sha256': 'map',
            'municipal_jurisdiction_sha256': 'jur', 'sidewalk_sha256': 'sidewalk',
            'fixture_identity_sha256': 'fi', 'fixture_geometry_sha256': 'fg',
            'curb_sha256': 'curb', 'one_way_direction_sha256': 'way',
            'fixture_blueprint_sha256': 'bp', 'fixture_kind': 'sidewalk_elevator',
            'fixture_physical_support': 'spawned_prop',
            'fixture': {'west_x_m': 10.0, 'east_x_m': 12.0, 'curb_y_m': 1.0,
                        'sidewalk_depth_m': 2.0}, 'curb_y_m': 1.0,
            'approach_waypoints': [[0.0, 0.0], [20.0, 0.0]],
            'ego_blueprint_sha256': 'ego-bp', 'camera_plan_sha256': 'camera',
            'traffic_conflict_source_sha256': 'traffic', 'police_direction_source_sha256': 'police',
            'traffic_device_source_sha256': 'device'}


def rows(case):
    base = {'case_id': case.id, 'ego_id': 'ego', 'fixture_id': 'fixture',
            'map_sha256': 'map', 'fixture_identity_sha256': 'fi',
            'fixture_geometry_sha256': 'fg', 'camera_plan_sha256': 'camera',
            'jurisdiction_sha256': 'jur', 'source_sha256': 'src',
            'frame_map_sha256': 'fm', 'body_west_x_m': 13.374,
            'body_east_x_m': 17.374, 'body_curb_gap_m': 0.3,
            'ego_speed_mps': 0.0, 'activity_observation': 'parked',
            'exception_source_sha256': 'exception' if case.exception != 'none' else None}
    return [dict(base, original_frame=i) for i in range(2)]


class ParkingTests(unittest.TestCase):
    def test_site_requires_physical_fixture_and_source(self):
        s = site()
        p.validate_site(s)
        s['fixture_physical_support'] = 'none'
        with self.assertRaisesRegex(ValueError, 'physical support'):
            p.validate_site(s)
        s = site()
        s['fixture_geometry_sha256'] = None
        with self.assertRaisesRegex(ValueError, 'geometry.*source missing'):
            p.validate_site(s)

    def test_numeric_boundary_both_sides(self):
        s = site()
        for region in ('west', 'east'):
            cases = [next(c for c in p.CASES if c.id == f'{region}_{suffix}')
                     for suffix in ('inside', 'at', 'outside')]
            measured_gaps = []
            for case in cases:
                lo, hi = p.target_body_interval(s, case, 4.0)
                observed_region, gap = p._gap(lo, hi, 10.0, 12.0)
                self.assertEqual(observed_region, region)
                measured_gaps.append(gap)
            for observed, target in zip(measured_gaps, [1.374, 1.524, 1.674]):
                self.assertAlmostEqual(observed, target)

    def test_construction_readback_exception_and_cleanup(self):
        s = site()
        a = Adapter()
        case = next(c for c in p.CASES if c.id == 'front_police_exception')
        built = p.build_case(a, s, case, 4.0)
        self.assertEqual(built['owned'], ('fixture', 'ego'))
        self.assertTrue(any(c[0] == 'exception' for c in a.calls))
        self.assertTrue(any(c[0] == 'curb' for c in a.calls))
        bad = Adapter(bad_readback=True)
        with self.assertRaisesRegex(ValueError, 'geometry readback'):
            p.build_case(bad, s, case, 4.0)
        self.assertEqual(bad.calls[-1], ('destroy', 'fixture'))
        s['police_direction_source_sha256'] = None
        a = Adapter()
        with self.assertRaisesRegex(ValueError, 'police_direction source missing'):
            p.build_case(a, s, case, 4.0)
        self.assertEqual(a.calls[-2:], [('destroy', 'ego'), ('destroy', 'fixture')])

    def test_original_measurement_and_missing_source(self):
        s = site()
        case = next(c for c in p.CASES if c.id == 'east_inside')
        result = p.measure_original_history(rows(case), s, case)
        self.assertAlmostEqual(result['min_side_gap_m'], 1.374)
        self.assertEqual(result['observed_regions'], ['east'])
        self.assertIsNone(result['legal_judgment'])
        damaged = rows(case)
        damaged[1]['original_frame'] = 3
        with self.assertRaisesRegex(ValueError, 'frame join'):
            p.measure_original_history(damaged, s, case)
        damaged = rows(case)
        damaged[1]['fixture_geometry_sha256'] = 'other'
        with self.assertRaisesRegex(ValueError, 'fixed source changed'):
            p.measure_original_history(damaged, s, case)

    def test_comparison_rejects_fixed_change(self):
        base = {'case_id': 'a', 'frame_count': 900, 'original_history_sha256': 'a',
                'source_identity': {'map_sha256': 'map', 'fixture_identity_sha256': 'fi',
                                    'fixture_geometry_sha256': 'fg', 'camera_plan_sha256': 'cam',
                                    'jurisdiction_sha256': 'jur'}, 'camera_plan_sha256': 'cam',
                'ego_blueprint_sha256': 'bp', 'weather_sha256': 'weather',
                'route_sha256': 'route', 'curb_gap_target_m': 0.3, 'side_gap_target_m': 1.374}
        other = dict(base, case_id='b', original_history_sha256='b', side_gap_target_m=1.524)
        p.audit_comparison(base, other, 'side_gap_target_m')
        other['weather_sha256'] = 'rain'
        with self.assertRaisesRegex(ValueError, 'fixed condition'):
            p.audit_comparison(base, other, 'side_gap_target_m')
        other = dict(base, case_id='b', original_history_sha256='b')
        with self.assertRaisesRegex(ValueError, 'difference absent'):
            p.audit_comparison(base, other, 'side_gap_target_m')


if __name__ == '__main__':
    unittest.main()
