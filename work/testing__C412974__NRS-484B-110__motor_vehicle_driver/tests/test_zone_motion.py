"""Synthetic geometry and source-rejection checks; not physical evidence."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zone_motion import CASES, intersection_area, measure_original, validate_scene

SOURCE_SHA = 'a' * 64


def make_scene(case):
    end = {'through': [20.0, 1.0], 'within': [5.0, 1.0], 'beside': [20.0, 5.0]}[case.route]
    start = [-10.0, 5.0 if case.route == 'beside' else 1.0]
    route = [start, [5.0, start[1]], end]
    scene = {
        'cell_id': 'C412974', 'actor': 'motor_vehicle_driver',
        'driver_present': True, 'motor_vehicle': True,
        'highway_public_access': True, 'highway_dedicated_public_authority': True,
        'zone_designation_status': case.designation,
        'official_pedestrian_exclusive': True if case.designation == 'active' else None,
        'marking_or_sign_visible': True if case.designation == 'active' else None,
        'designation_interval_s': [0, 45] if case.designation == 'active' else None,
        'route_variant': case.route, 'zone_rect_m': [0.0, 0.0, 10.0, 2.0],
        'vehicle_start_xy': start, 'vehicle_target_xy': end, 'vehicle_route_xy': route,
    }
    for name in ('map', 'highway', 'zone_boundary', 'designation', 'marking',
                 'vehicle', 'driver', 'route'):
        scene[name + '_source_sha256'] = SOURCE_SHA
    return scene


def make_rows(scene, case):
    start, end = scene['vehicle_start_xy'], scene['vehicle_target_xy']
    rows = []
    for i in range(900):
        fraction = i / 899
        x = start[0] + (end[0] - start[0]) * fraction
        y = start[1] + (end[1] - start[1]) * fraction
        body = [x - 0.5, y - 0.4, x + 0.5, y + 0.4]
        row = {
            'original_frame': 1200 + i, 'time_s': 60 + i / 20,
            'vehicle_id': 'synthetic-ego', 'vehicle_body_rect_m': body,
            'vehicle_speed_mps': 4.0,
            'zone_overlap_area_m2': intersection_area(body, scene['zone_rect_m']),
        }
        for name in ('frame', 'vehicle_body', 'vehicle_motion', 'zone_boundary',
                     'designation', 'marking_visibility'):
            row[name + '_source_sha256'] = SOURCE_SHA
        rows.append(row)
    return rows


class ZoneMotionTests(unittest.TestCase):
    def test_all_exact_routes_and_original_measurement(self):
        for case in CASES:
            with self.subTest(case=case.name):
                scene = make_scene(case)
                validate_scene(scene, case)
                result = measure_original(make_rows(scene, case), scene, case)
                self.assertEqual(result['frame_count'], 900)
                self.assertIsNone(result['legal_judgment'])
                self.assertEqual(result['overlap_frame_count'] > 0, case.route != 'beside')
                self.assertEqual(result['terminal_center_within'], case.route == 'within')

    def test_required_source_and_physical_path_rejections(self):
        case = CASES[0]
        scene = make_scene(case)
        scene['designation_source_sha256'] = None
        with self.assertRaisesRegex(ValueError, 'original source missing'):
            validate_scene(scene, case)
        scene = make_scene(case)
        scene['vehicle_route_xy'][1] = [5.0, 5.0]
        with self.assertRaisesRegex(ValueError, 'through-zone route'):
            validate_scene(scene, case)
        scene = make_scene(case)
        rows = make_rows(scene, case)
        rows[17]['vehicle_body_source_sha256'] = None
        with self.assertRaisesRegex(ValueError, 'original frame source missing'):
            measure_original(rows, scene, case)
        rows = make_rows(scene, case)
        rows[20]['zone_overlap_area_m2'] += 1
        with self.assertRaisesRegex(ValueError, 'zone overlap differs'):
            measure_original(rows, scene, case)


if __name__ == '__main__':
    unittest.main()
