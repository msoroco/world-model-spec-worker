import json
from hashlib import sha256
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from marked_course_finalizer import analyze, build_result, ASSIGNMENT, CAMERAS
from test_marked_course_measurement import fixture


class MarkedCourseFinalizerTests(unittest.TestCase):
    def prepare(self, root):
        scene, bodies = fixture(root)
        case = ASSIGNMENT + '__indicated_course'
        scene['case_id'] = case
        (root / 'marked_intersection.json').write_text(json.dumps(scene))
        frames = [json.loads(line) for line in (root / 'video_frames.jsonl').read_text().splitlines()]
        (root / 'trace.jsonl').write_text(''.join(json.dumps({'frame': row['carla_frame'],
            'time_s': row['time_s'], 'position_m': [float(index), 0.]}) + '\n'
            for index, row in enumerate(frames)))
        for name in CAMERAS:
            (root / name).write_bytes(b'original source placeholder')
        config = {'selected_case_id': case, 'law_id': 'LVMC-11-12-020',
                  'cell_id': 'C126064', 'actor': 'motor_vehicle_driver',
                  'case': {'recording_description': {'channels': [
                      {'name': 'original_marked_turn_course', 'unit': 'structured'}]}}}
        (root / 'config.json').write_text(json.dumps(config))
        return case

    def test_saved_sources_create_channel_without_legal_claim(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            case = self.prepare(root)
            report = analyze(root)
            result = build_result(root, report)
            self.assertEqual(report['case_id'], case)
            self.assertEqual(report['measurements']['original_marked_turn_course']['value']['frame_count'], 3)
            self.assertEqual(result['recording_evidence'][0]['reference'], 'original_marked_turn_course.jsonl')
            self.assertFalse(result['setup_confirmed'])
            self.assertFalse(report['legal_acceptance_claimed'])

    def test_rejects_missing_camera_and_changed_trace_join(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.prepare(root)
            (root / CAMERAS[0]).unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source: overview.mkv'):
                analyze(root)
            (root / CAMERAS[0]).write_bytes(b'original source placeholder')
            trace = [json.loads(line) for line in (root / 'trace.jsonl').read_text().splitlines()]
            trace[0]['frame'] = 99
            (root / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in trace))
            with self.assertRaisesRegex(ValueError, 'trace join differs'):
                analyze(root)

    def test_nonmarker_forms_use_original_readback_and_exact_identity(self):
        for form in ('button', 'other_indication'):
            with self.subTest(form=form), TemporaryDirectory() as directory:
                root = Path(directory)
                self.prepare(root)
                case = ASSIGNMENT + '__' + form + '_indicated_course'
                scene = json.loads((root / 'marked_intersection.json').read_text())
                scene['case_id'] = case
                scene.pop('physical_markers_xy_m')
                scene['indication_form'] = form
                scene['physical_indications_xy_m'] = [[1.0, 1.0]]
                authority = json.loads((root / 'authority_source_original.json').read_text())
                authority['indication_form'] = form
                authority['indications'] = [{'form': form, 'x': 1, 'y': 1}]
                original = json.dumps(authority).encode()
                (root / 'authority_source_original.json').write_bytes(original)
                scene['authority_source_sha256'] = sha256(original).hexdigest()
                (root / 'marked_intersection.json').write_text(json.dumps(scene))
                config = json.loads((root / 'config.json').read_text())
                config['selected_case_id'] = case
                (root / 'config.json').write_text(json.dumps(config))
                report = analyze(root)
                self.assertEqual(report['measurements']['original_marked_turn_course']['value']['indication_form'], form)
                self.assertIn(form, build_result(root, report)['target_checks'][0]['method'])
                scene['indication_form'] = 'marker'
                (root / 'marked_intersection.json').write_text(json.dumps(scene))
                with self.assertRaisesRegex(ValueError, 'non-marker readback'):
                    analyze(root, write_channel=False)


if __name__ == '__main__':
    unittest.main()
