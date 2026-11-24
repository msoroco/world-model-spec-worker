import json
from pathlib import Path
import unittest

from runner import CAMERAS, FRAMES, check
from route_meter import measure


class OfflineRouteTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_exact_contract(self):
        report = check(self.config)
        self.assertEqual(report['frames'], FRAMES)
        self.assertEqual(len(report['cameras']), 4)
        self.assertEqual(len(set(report['cameras'])), 4)
        self.assertFalse(report['native_imported'])

    def test_route_meter_distinguishes_controlled_conditions(self):
        context = {'source_kind': 'synthetic_cpu_fixture', 'expected_frames': FRAMES,
                   'origin_curb_xy_m': [[-3.5, -20], [-3.5, 20]],
                   'opposite_curb_xy_m': [[3.5, -20], [3.5, 20]],
                   'crosswalk_polygons_xy_m': []}
        y = 0 if self.config['condition'] == 'right_angle' else 2.8
        samples = [{'native_frame': 10 + i,
                    'pedestrian_xy_m': [-3.5 + 7 * i / (FRAMES - 1), y * i / (FRAMES - 1)]}
                   for i in range(FRAMES)]
        result = measure(samples, context)
        self.assertEqual(result['legal_verdict'], 'not_assigned')
        if self.config['condition'] == 'right_angle':
            self.assertLess(result['right_angle_deviation_deg'], 1e-7)
            self.assertLess(result['route_excess_length_m'], 1e-7)
        else:
            self.assertGreater(result['right_angle_deviation_deg'], 10)
            self.assertGreater(result['route_excess_length_m'], .3)

    def test_mutated_config_rejected(self):
        self.config['duration_s'] = 29
        with self.assertRaisesRegex(ValueError, 'Full crossing window differs'):
            check(self.config)

    def test_missing_source_position_rejected(self):
        context = {'source_kind': 'synthetic_cpu_fixture', 'expected_frames': FRAMES,
                   'origin_curb_xy_m': [[-3.5, -20], [-3.5, 20]],
                   'opposite_curb_xy_m': [[3.5, -20], [3.5, 20]]}
        samples = [{'native_frame': i, 'pedestrian_xy_m': [i / 100, 0]} for i in range(FRAMES)]
        samples[50].pop('pedestrian_xy_m')
        with self.assertRaisesRegex(ValueError, 'Original pedestrian position missing'):
            measure(samples, context)


if __name__ == '__main__':
    unittest.main()
