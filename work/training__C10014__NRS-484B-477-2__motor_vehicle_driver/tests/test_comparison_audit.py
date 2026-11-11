"""Metadata isolation tests using source-shaped values, never Native evidence."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_audit import compare_fixed_inputs


def shaped(stop):
    return {
        'config': {'candidate_id':'primary','cell_id':'C10014',
                   'law_id':'NRS-484B-477-2','actor':'motor_vehicle_driver',
                   'duration_s':24,'rate_hz':20,'cameras':['four declared views'],
                   'case_id':'unit-'+str(stop)},
        'road_geometry': {'native_map_sha256':'same-map',
                          'entrance_bounds_m':[-3,-4,3,0]},
        'runner_sha256':'same-runner',
        'native_context': {'native_weather_readback':{'sun_altitude_angle':45},
                           'vehicle_blueprint':'vehicle.lincoln.mkz_2020',
                           'controller_knobs':{'target_speed_mps':5},
                           'requested_stop_x_m':stop,
                           'requested_route_points':100 if stop == -12 else 220},
    }


class ComparisonIsolationTest(unittest.TestCase):
    def test_exact_declared_stop_station_pair(self):
        self.assertEqual(compare_fixed_inputs(shaped(-12), shaped(0))
                         ['declared_difference'], 'commanded_stop_station_m')

    def test_camera_weather_and_controller_changes_rejected(self):
        for area, key, value in (
            ('config', 'cameras', ['changed view']),
            ('native_context', 'native_weather_readback', {'sun_altitude_angle':0}),
            ('native_context', 'controller_knobs', {'target_speed_mps':8}),
        ):
            contrast = deepcopy(shaped(0))
            contrast[area][key] = value
            with self.subTest(area=area, key=key), self.assertRaises(ValueError):
                compare_fixed_inputs(shaped(-12), contrast)

    def test_candidate_and_stop_target_changes_rejected(self):
        contrast = shaped(0)
        contrast['config']['candidate_id'] = 'fallback1'
        with self.assertRaisesRegex(ValueError, 'different fallback'):
            compare_fixed_inputs(shaped(-12), contrast)
        with self.assertRaisesRegex(ValueError, 'stop-station'):
            compare_fixed_inputs(shaped(-12), shaped(2))


if __name__ == '__main__':
    unittest.main()
