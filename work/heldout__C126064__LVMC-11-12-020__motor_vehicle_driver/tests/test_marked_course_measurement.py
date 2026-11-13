import json
from hashlib import sha256
from pathlib import Path
import subprocess
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
    authority = {key: scene[key] for key in (
        'municipal_jurisdiction_source', 'intersection_source', 'authorization_source',
        'median_opening_with_intersecting_road', 'intersection_polygon_xy_m',
        'indicated_course_xy_m')}
    original = json.dumps(authority).encode()
    (root / 'authority_source_original.json').write_bytes(original)
    scene['authority_source_sha256'] = sha256(original).hexdigest()
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
    def test_button_source_readback_is_measured_as_button(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            scene, _ = fixture(root)
            authority = json.loads((root / 'authority_source_original.json').read_text())
            authority['indication_form'] = 'button'
            authority['indications'] = [{'form': 'button', 'x': 1, 'y': 1}]
            original = json.dumps(authority).encode()
            (root / 'authority_source_original.json').write_bytes(original)
            scene.pop('physical_markers_xy_m')
            scene['indication_form'] = 'button'
            scene['physical_indications_xy_m'] = [[1.0, 1.0]]
            scene['authority_source_sha256'] = sha256(original).hexdigest()
            (root / 'marked_intersection.json').write_text(json.dumps(scene))
            result = measure(root, 'case')
            self.assertEqual(result['indication_form'], 'button')
            self.assertEqual(result['physical_indications_xy_m'], [[1.0, 1.0]])
            scene['physical_indications_xy_m'] = [[1.2, 1.0]]
            (root / 'marked_intersection.json').write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, 'readback differs'):
                measure(root, 'case')
            scene['physical_indications_xy_m'] = [[1.0, 1.0]]
            scene['indication_form'] = 'other_indication'
            (root / 'marked_intersection.json').write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, 'form differs'):
                measure(root, 'case')

    def test_original_footprint_and_authorized_marker_join(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            result = measure(root, 'case')
            self.assertEqual(result['frame_count'], 3)
            self.assertEqual(len(result['source_sha256']), 4)
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

    def test_saved_only_cli_replays_original_sources(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            output = root / 'analysis.json'
            script = Path(__file__).resolve().parents[1] / 'marked_course_measurement.py'
            subprocess.run([sys.executable, str(script), '--source-dir', str(root),
                            '--case-id', 'case', '--output', str(output)], check=True)
            self.assertEqual(json.loads(output.read_text())['frame_count'], 3)
            (root / 'turn_body.jsonl').unlink()
            failed = subprocess.run([sys.executable, str(script), '--source-dir', str(root),
                                     '--case-id', 'case', '--output', str(output)],
                                    capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn('Original marker, body, frame-map or authority source missing', failed.stderr)

    def test_missing_or_changed_original_authority_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            scene, _ = fixture(root)
            authority = root / 'authority_source_original.json'
            authority.unlink()
            with self.assertRaisesRegex(ValueError, 'authority source missing'):
                measure(root, 'case')
            fixture(root)
            authority.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'authority source hash changed'):
                measure(root, 'case')
            fixture(root)
            scene['indicated_course_xy_m'] = [[0, 0], [2, 0], [3, 3]]
            (root / 'marked_intersection.json').write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, 'differs from captured scene'):
                measure(root, 'case')


if __name__ == '__main__':
    unittest.main()
