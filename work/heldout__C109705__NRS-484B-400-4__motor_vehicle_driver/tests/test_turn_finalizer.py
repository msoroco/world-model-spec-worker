"""Retained-source joins for C109705 saved turn measurement."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from turn_finalizer import analyze
from turn_native_runner import PREFIX


class TurnFinalizerTests(unittest.TestCase):
    def fixture(self, root):
        case = PREFIX + 'approach_near_depart_right'
        config = {'law_id': 'NRS-484B-400-4', 'cell_id': 'C109705',
                  'actor': 'motor_vehicle_driver', 'selected_case_id': case,
                  'case': {'case_id': case}, 'rate_hz': 20, 'frames': 160,
                  'cameras': [{}] * 4}
        (root / 'config.json').write_text(json.dumps(config))
        geometry = {'source_directionality': 'one_way', 'destination_directionality': 'two_directional',
                    'maneuver': 'left_turn', 'intersection_id': 'junction-1',
                    'map_source': 'original-map-readback', 'source_left_curb': [[0, 0], [0, 10]],
                    'destination_centerline': [[0, 0], [10, 0]]}
        (root / 'road_geometry.json').write_text(json.dumps(geometry))
        frames = []
        for index, (phase, corners) in enumerate((
                ('approach', [[.5, 1], [1, 1], [1, 2], [.5, 2]]),
                ('inside_intersection', [[1, 1], [2, 1], [2, 2], [1, 2]]),
                ('leaving_intersection', [[1, -1], [2, -1], [2, -2], [1, -2]]))):
            frames.append({'frame': index + 100, 'time_s': index * .05,
                           'subject_id': 'ego', 'phase': phase, 'ground_corners': corners})
        (root / 'body_footprints.json').write_text(json.dumps({'subject_id': 'ego', 'frames': frames}))
        (root / 'body_footprints.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in frames))
        (root / 'video_frames.jsonl').write_text(''.join(json.dumps({
            'video_frame': index, 'carla_frame': row['frame'], 'time_s': row['time_s']}) + '\n'
            for index, row in enumerate(frames)))
        (root / 'trace.jsonl').write_text(''.join(json.dumps({
            'frame': row['frame'], 'time_s': row['time_s']}) + '\n' for row in frames))

    def test_original_turn_join_and_missing_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            report = analyze(root)
            observed = report['measurements']['turn_geometry']['value']
            self.assertTrue(observed['departure_all_corners_right_of_centerline'])
            self.assertTrue((root / 'approach_left_curb_distance_m.jsonl').is_file())
            (root / 'road_geometry.json').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source: road_geometry.json'):
                analyze(root)

    def test_changed_original_footprint_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            rows = [json.loads(line) for line in (root / 'body_footprints.jsonl').read_text().splitlines()]
            rows[1]['time_s'] = 9
            (root / 'body_footprints.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'footprint, trace and frame-map lengths differ'):
                analyze(root)


if __name__ == '__main__':
    unittest.main()
