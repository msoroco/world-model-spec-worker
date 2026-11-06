"""Self-contained CPU preflight for each exact materialized C10052 bundle."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engineering import NAMES, TRIGGERS, parameters
from geometry import body, check, route
from measure_facility import measure, overlap_area
from runner import check as runner_check


class ExactBundleTests(unittest.TestCase):
    def test_exact_runner_preflight(self):
        config = json.loads((ROOT/'config.json').read_text())
        result = runner_check(config)
        self.assertFalse(result['native_imported'])
        self.assertFalse(result['physical_success_claimed'])
        self.assertEqual(result['camera_count'], 4)

    def test_map_route_and_distinct_fallbacks(self):
        self.assertEqual(check()['roads'], [1, 2])
        self.assertEqual(route('probe_a')[:151], route('probe_b')[:151])
        base = parameters('probe_b', 'primary')
        changed = [{key for key in base if base[key] != parameters('probe_b', name)[key]}
                   for name in NAMES[1:]]
        self.assertEqual(len({frozenset(s) for s in changed}), 3)
        self.assertTrue(all(TRIGGERS[name]['source'] and TRIGGERS[name]['metric']
                            for name in NAMES[1:]))

    def test_original_source_positive_and_missing_context_negative(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            geometry = {'road_id': 1, 'driving_lane_id': -1, 'bicycle_lane_id': -2,
                        'bicycle_facility_native_xy_bounds_m': [-60, -5, 60, -3],
                        'alley_entrance_native_xy_bounds_m': [-3, -14, 3, -5],
                        'native_facility_design_verified': False}
            (folder/'road_geometry.json').write_text(json.dumps(geometry))
            rows = [{'native_frame': 100+i, 'time_s': (i+1)/20,
                     'native_center_xy_m': [-12, -4], 'native_forward_xy': [1, 0],
                     'native_body_xy_m': body(-12, -4), 'native_road_id': 1,
                     'native_lane_id': -2, 'speed_mps': 0.0} for i in range(40)]
            (folder/'native_samples.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.assertRaisesRegex(ValueError, 'Missing required source: exception_context.json'):
                measure(folder/'native_samples.jsonl', folder/'road_geometry.json',
                        folder/'exception_context.json')
            flags = {key: False for key in ('entering_or_exiting_alley_or_driveway',
                'disabled_vehicle', 'avoiding_traffic_conflict', 'official_duties',
                'police_direction', 'emergency')}
            (folder/'exception_context.json').write_text(json.dumps({
                'source_kind': 'synthetic_scene_request', 'exceptions': flags}))
            value = measure(folder/'native_samples.jsonl', folder/'road_geometry.json',
                            folder/'exception_context.json')
            self.assertEqual(value['max_stopped_overlap_m2'], 9.36)
            self.assertEqual(value['observed_exception_status'], 'unresolved')

    def test_rotated_body_clipping(self):
        forward = (math.cos(math.radians(20)), math.sin(math.radians(20)))
        self.assertGreater(overlap_area(body(-12, -4, forward), (-60, -5, 60, -3)), 0)
        self.assertEqual(overlap_area(body(-12, -1.5), (-60, -5, 60, -3)), 0)


if __name__ == '__main__':
    unittest.main()
