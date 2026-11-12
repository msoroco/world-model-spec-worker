import json
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


if __name__ == '__main__':
    unittest.main()
