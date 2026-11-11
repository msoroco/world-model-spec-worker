import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overtake_comparison_audit import audit
from test_overtake_measurement import box


PREFIX = 'heldout__C110161__NRS-484B-207-1__motor_vehicle_driver__'


def attempt(root, suffix, *, lateral=4, return_x=12, left_target=2,
            return_target=3):
    root.mkdir()
    config = {
        'selected_case_id': PREFIX + suffix,
        'law_id': 'NRS-484B-207-1', 'cell_id': 'C110161',
        'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'frames': 4,
        'map_name': 'Town', 'route_direction': 'east',
        'right_lane_id': 1, 'left_lane_id': 2,
        'subject_blueprint': 'vehicle.tesla.model3',
        'other_blueprint': 'vehicle.tesla.model3',
        'subject_speed_mps': 8, 'other_speed_mps': 4,
        'cameras': ['overview', 'approach', 'reference_corner', 'driver_reference'],
        'required_atoms': [], 'source_packets': [],
        'target_left_gap_m': left_target,
        'requested_return_clearance_m': return_target,
    }
    (root / 'config.json').write_text(json.dumps(config))
    rows = []
    for i, (ego_x, ego_y) in enumerate(((0, lateral), (5, lateral),
                                        (10, lateral), (return_x, 2))):
        rows.append({'frame': 100 + i, 'time_s': i * .05,
                     'ego_id': 'ego', 'other_id': 'other',
                     'road_tangent_xy': [1, 0],
                     'ego_heading_xy': [1, 0], 'other_heading_xy': [1, 0],
                     'ego_corners': box(ego_x, ego_x + 4, ego_y, ego_y + 2),
                     'other_corners': box(5, 9, 0, 2)})
    (root / 'participant_footprints.jsonl').write_text(
        ''.join(json.dumps(row) + '\n' for row in rows))


class OvertakeComparisonAuditTests(unittest.TestCase):
    def test_left_clearance_comparison_and_fixed_return_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / 'wide', Path(directory) / 'narrow'
            attempt(first, 'left_pass_wide', lateral=5, left_target=3)
            attempt(second, 'left_pass_narrow', lateral=4, left_target=2)
            result = audit('left_pass_clearance', first, second)
            self.assertEqual(result['measured_values'], [3, 2])
            self.assertFalse(result['legal_acceptance_claimed'])
            config = json.loads((second / 'config.json').read_text())
            config['requested_return_clearance_m'] = 5
            (second / 'config.json').write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, 'Fixed comparison condition'):
                audit('left_pass_clearance', first, second)

    def test_return_order_and_missing_source_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / 'before', Path(directory) / 'after'
            attempt(first, 'return_before_clear', return_x=8, return_target=-1)
            attempt(second, 'return_after_clear', return_x=12, return_target=3)
            result = audit('return_clearance_order', first, second)
            self.assertEqual(result['measured_values'], [-1, 3])
            (second / 'participant_footprints.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing original comparison'):
                audit('return_clearance_order', first, second)


if __name__ == '__main__':
    unittest.main()
