import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('physical_geometry_audit',
                                               ROOT / 'physical_geometry_audit.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def scene(name):
    return json.loads((ROOT / 'cases' / name / 'scene.json').read_text())


def rows(start, end):
    result = []
    for i in range(400):
        t = i / 399
        x = start[0] + t * (end[0] - start[0])
        y = start[1] + t * (end[1] - start[1])
        result.append({'frame': 5000 + i, 'time_s': 40 + i / 20,
                       'actor_id': 17, 'source': 'original_native',
                       'source_kind': 'original_native_world_vertices',
                       'body_center_xy_m': [x, y],
                       'body_xy_m': [[x - 0.1, y - 0.1], [x + 0.1, y - 0.1],
                                     [x + 0.1, y + 0.1], [x - 0.1, y + 0.1]]})
    return result


class BodyGeometryTests(unittest.TestCase):
    def test_completion_three_source_states(self):
        s = scene('outside_right_angle')
        complete = mod.evaluate_crossing_completion(s, rows(s['route_xy_m'][0], s['route_xy_m'][-1]))
        self.assertEqual(complete['physical_checks']['maneuver']['status'], 'met')
        self.assertTrue(complete['maneuver_completed'])
        midpoint = [(a + b) / 2 for a, b in zip(s['route_xy_m'][0], s['route_xy_m'][-1])]
        incomplete = mod.evaluate_crossing_completion(s, rows(s['route_xy_m'][0], midpoint))
        self.assertEqual(incomplete['physical_checks']['maneuver']['status'], 'not_met')
        self.assertFalse(incomplete['maneuver_completed'])
        missing = mod.evaluate_crossing_completion(s, None)
        self.assertEqual(missing['physical_checks']['maneuver']['status'], 'unverified')
        self.assertFalse(missing['maneuver_completed'])

    def test_outside_and_inside_full_duration_original_body(self):
        for name in ('outside_right_angle', 'inside_crosswalk_oblique'):
            s = scene(name)
            report = mod.audit_body_history(s, rows(s['route_xy_m'][0], s['route_xy_m'][-1]))
            self.assertEqual(report['frame_count'], 400)
            self.assertEqual(report['first_original_frame'], 5000)
            self.assertEqual(report['last_original_frame'], 5399)
            self.assertEqual(bool(report['body_crosswalk_overlap_frames']),
                             s['crosswalk_context'] == 'inside')
            self.assertEqual(report['legal_route_classification'], 'unresolved')

    def test_crosswalk_body_overlap_rejected_when_center_stays_outside(self):
        s = scene('outside_right_angle')
        s['crosswalk_boundaries_xy_m'] = [[[5.15, 2], [5.5, 2],
                                           [5.5, 4], [5.15, 4]]]
        original = rows(s['route_xy_m'][0], s['route_xy_m'][-1])
        original[200]['body_xy_m'] = [[4.9, 2.9], [5.3, 2.9],
                                      [5.3, 3.1], [4.9, 3.1]]
        with self.assertRaisesRegex(ValueError, 'body and crosswalk context disagree'):
            mod.audit_body_history(s, original)

    def test_missing_body_source_and_time_gap_rejected(self):
        s = scene('outside_right_angle')
        original = rows(s['route_xy_m'][0], s['route_xy_m'][-1])
        original[200]['source_kind'] = 'requested_waypoint'
        with self.assertRaisesRegex(ValueError, 'original Native body source'):
            mod.audit_body_history(s, original)
        original = rows(s['route_xy_m'][0], s['route_xy_m'][-1])
        original[200]['time_s'] += 0.1
        with self.assertRaisesRegex(ValueError, '20 Hz time join'):
            mod.audit_body_history(s, original)


if __name__ == '__main__':
    unittest.main()
