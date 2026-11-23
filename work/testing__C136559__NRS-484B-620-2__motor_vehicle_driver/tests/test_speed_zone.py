import importlib.util
import pathlib
import unittest

MODULE = pathlib.Path(__file__).resolve().parents[1] / 'speed_zone.py'
spec = importlib.util.spec_from_file_location('speed_zone', MODULE)
mod = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def site():
    return {'cell_id': 'C136559', 'layout': 'narrow_road',
            'road_source_sha256': 'road', 'zone_establishment_source_sha256': 'order',
            'public_access_source_sha256': 'access', 'boundary_source_sha256': 'boundary',
            'authorized_speed_mph': 25.0, 'zone_extent_source_sha256': 'extent',
            'sign_instruction_source_sha256': 'instruction',
            'vehicle_class': 'self_propelled_nonrail_motor_vehicle',
            'lanes': {'eastbound': {'lane_id': 'e', 'source_sha256': 'e', 'waypoints': [1, 2]},
                      'westbound': {'lane_id': 'w', 'source_sha256': 'w', 'waypoints': [3, 4]}},
            'signs': {'eastbound': {'source_sha256': 'se'},
                      'westbound': {'source_sha256': 'sw'}}}


class Adapter:
    def __init__(self):
        self.calls = []
    def spawn_vehicle(self, point, **kwargs):
        self.calls.append(('vehicle', point, kwargs))
        return 'ego'
    def install_sign(self, spec, **kwargs):
        self.calls.append(('sign', spec, kwargs))
        self.enabled = kwargs['enabled']
        return 'sign'
    def read_sign(self, sign):
        return {'source_sha256': 'native', 'direction': self.direction,
                'installed': self.enabled}
    def set_route(self, actor, route, **kwargs):
        self.calls.append(('route', actor, route, kwargs))
    def destroy(self, actor):
        self.calls.append(('destroy', actor))


def rows(case):
    return [{'original_frame': i, 'original_time_s': i / 20,
             'source_sha256': 'capture', 'zone_establishment_source_sha256': 'order',
             'zone_extent_source_sha256': 'extent', 'sign_readback_source_sha256': 'sign',
             'map_source_sha256': 'map', 'ego_id': 'ego',
             'vehicle_class': 'self_propelled_nonrail_motor_vehicle',
             'direction': case.direction, 'sign_direction': case.direction,
             'actual_speed_mps': 11.0 + i / 10, 'inside_zone': case.zone_mode != 'outside',
             'sign_installed': case.zone_mode != 'sign_absent'} for i in range(3)]


def pair(case):
    return {'case_id': case.case_id, 'road_source_sha256': 'road', 'map_source_sha256': 'map',
            'zone_establishment_source_sha256': 'order', 'zone_extent_source_sha256': 'extent',
            'sign_instruction_source_sha256': 'instruction', 'ego_blueprint': 'car',
            'weather_sha256': 'weather', 'camera_plan_sha256': 'camera',
            'duration_frames': 900, 'requested_mph': case.requested_mph,
            'zone_mode': case.zone_mode, 'direction': case.direction,
            'original_history_sha256': case.case_id}


class SpeedZoneTest(unittest.TestCase):
    def test_all_cases_construct(self):
        for case in mod.CASES:
            with self.subTest(case=case.case_id):
                adapter = Adapter()
                adapter.direction = case.direction
                out = mod.build_case(adapter, site(), case)
                self.assertEqual(out['case_id'], case.case_id)
                self.assertEqual(adapter.calls[0][1], site()['lanes'][case.direction]['waypoints'][0])
                self.assertAlmostEqual(adapter.calls[2][3]['target_speed_mps'], case.requested_mph * .44704)
                self.assertEqual(adapter.calls[1][2]['enabled'], case.zone_mode != 'sign_absent')

    def test_site_rejects_wrong_direction_lane(self):
        s = site()
        s['lanes']['westbound']['lane_id'] = 'e'
        with self.assertRaisesRegex(ValueError, 'share lane'):
            mod.validate_site(s, mod.CASES[-1])

    def test_site_rejects_missing_zone_order(self):
        s = site()
        s['zone_establishment_source_sha256'] = ''
        with self.assertRaisesRegex(ValueError, 'source missing'):
            mod.validate_site(s, mod.CASES[0])

    def test_measure_retains_original_history_and_unknown_judgment(self):
        result = mod.measure_original(rows(mod.CASES[2]), mod.CASES[2])
        self.assertEqual(result['actual_speed_mps_history'], [11.0, 11.1, 11.2])
        self.assertIsNone(result['sign_appropriateness_judgment'])
        self.assertEqual(result['frame_count'], 3)

    def test_measure_rejects_missing_sign_source(self):
        sample = rows(mod.CASES[0])
        sample[1]['sign_readback_source_sha256'] = ''
        with self.assertRaisesRegex(ValueError, 'original source missing'):
            mod.measure_original(sample, mod.CASES[0])

    def test_measure_rejects_frame_gap(self):
        sample = rows(mod.CASES[0])
        sample[2]['original_frame'] = 4
        with self.assertRaisesRegex(ValueError, 'frame discontinuity'):
            mod.measure_original(sample, mod.CASES[0])

    def test_audit_speed_only(self):
        mod.audit_pair(pair(mod.CASES[0]), pair(mod.CASES[2]), {'requested_mph'})

    def test_audit_rejects_fixed_weather(self):
        other = pair(mod.CASES[2])
        other['weather_sha256'] = 'rain'
        with self.assertRaisesRegex(ValueError, 'fixed condition changed'):
            mod.audit_pair(pair(mod.CASES[0]), other, {'requested_mph'})

    def test_audit_rejects_missing_original(self):
        other = pair(mod.CASES[2])
        other.pop('original_history_sha256')
        with self.assertRaisesRegex(ValueError, 'comparison source missing'):
            mod.audit_pair(pair(mod.CASES[0]), other, {'requested_mph'})
