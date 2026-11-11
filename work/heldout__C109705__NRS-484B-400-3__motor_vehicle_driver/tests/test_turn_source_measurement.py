import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from turn_source_measurement import measure


CASE = 'heldout__C109705__NRS-484B-400-3__motor_vehicle_driver__reference'


def fixture(root):
    geometry = {'case_id': CASE, 'ego_actor_id': 7, 'approach_directions': 2,
                'destination_directions': 1, 'maneuver': 'left_turn',
                'intersection_kind': 'public_highway_non_alley',
                'approach_centerline_xy_m': [[0, -10], [0, 0]],
                'destination_left_curb_xy_m': [[0, -3], [-10, -3]],
                'intersection_entry_xy_m': [0, 0]}
    (root / 'turn_road_geometry.json').write_text(json.dumps(geometry))
    frames = [{'video_frame': i, 'carla_frame': 100 + i, 'time_s': i / 20}
              for i in range(3)]
    bodies = [{'frame': 100 + i, 'time_s': i / 20, 'actor_id': 7,
               'phase': phase, 'body_corners_xy_m':
               [[0.5, -1 - i], [1.5, -1 - i], [1.5, -2 - i], [0.5, -2 - i]]}
              for i, phase in enumerate(('approach', 'entry', 'departure'))]
    for name, values in [('video_frames.jsonl', frames), ('body_footprints.jsonl', bodies)]:
        (root / name).write_text(''.join(json.dumps(row) + '\n' for row in values))
    return geometry, frames, bodies


class OriginalTurnSourceTests(unittest.TestCase):
    def test_complete_original_join_and_descriptive_measurements(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            result = measure(root, CASE)
            self.assertEqual(result['frame_count'], 3)
            self.assertTrue(result['entry_all_original_corners_right_of_centerline'])
            self.assertEqual(result['approach_nearest_corner_offset_m'], 0.5)
            self.assertFalse(result['legal_practicability_decided'])
            self.assertEqual(len(result['source_sha256']), 3)

    def test_missing_phase_wrong_direction_and_stale_actor_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            geometry, _, bodies = fixture(root)
            geometry['destination_directions'] = 2
            (root / 'turn_road_geometry.json').write_text(json.dumps(geometry))
            with self.assertRaisesRegex(ValueError, 'directions'):
                measure(root, CASE)
            geometry['destination_directions'] = 1
            (root / 'turn_road_geometry.json').write_text(json.dumps(geometry))
            bodies[-1]['phase'] = 'entry'
            (root / 'body_footprints.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in bodies))
            with self.assertRaisesRegex(ValueError, 'intervals'):
                measure(root, CASE)
            bodies[-1]['phase'] = 'departure'
            bodies[-1]['actor_id'] = 99
            (root / 'body_footprints.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in bodies))
            with self.assertRaisesRegex(ValueError, 'actor identity'):
                measure(root, CASE)


if __name__ == '__main__':
    unittest.main()
