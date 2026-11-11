import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from marked_course_measurement import measure


def fixture(root):
    scene = {'case_id': 'case', 'municipal_jurisdiction_source': 'municipal-map',
             'intersection_source': 'native-map', 'authorization_source': 'authority-record',
             'median_opening_with_intersecting_road': True, 'ego_actor_id': 7,
             'intersection_polygon_xy_m': [[-2, -2], [4, -2], [4, 4], [-2, 4]],
             'physical_markers_xy_m': [[1, 1]],
             'indicated_course_xy_m': [[0, 0], [3, 0], [3, 3]]}
    (root / 'marked_intersection.json').write_text(json.dumps(scene))
    bodies = [{'frame': 10 + i, 'time_s': i / 20, 'actor_id': 7,
               'corners_xy_m': [[i, 0], [i + .4, 0], [i + .4, .4], [i, .4]]}
              for i in range(3)]
    frames = [{'video_frame': i, 'carla_frame': 10 + i, 'time_s': i / 20}
              for i in range(3)]
    for name, rows in [('turn_body.jsonl', bodies), ('video_frames.jsonl', frames)]:
        (root / name).write_text(''.join(json.dumps(row) + '\n' for row in rows))
    return scene, bodies


class MarkedCourseTests(unittest.TestCase):
    def test_original_footprint_and_authorized_marker_join(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            result = measure(root, 'case')
            self.assertEqual(result['frame_count'], 3)
            self.assertEqual(len(result['source_sha256']), 3)
            self.assertIsNone(result['direction_disobedience_legal_judgment'])
            self.assertTrue(all(row['inside_intersection'] for row in result['observations']))

    def test_outside_marker_and_wrong_actor_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            scene, bodies = fixture(root)
            scene['physical_markers_xy_m'] = [[9, 9]]
            (root / 'marked_intersection.json').write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, 'not inside'):
                measure(root, 'case')
            scene['physical_markers_xy_m'] = [[1, 1]]
            (root / 'marked_intersection.json').write_text(json.dumps(scene))
            bodies[0]['actor_id'] = 8
            (root / 'turn_body.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in bodies))
            with self.assertRaisesRegex(ValueError, 'identity'):
                measure(root, 'case')


if __name__ == '__main__':
    unittest.main()
