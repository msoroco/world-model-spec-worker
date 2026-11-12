import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from three_lane_finalizer import PREFIX, analyze, build_result
from audit_right_baseline_delivery import audit
from three_lane_source_capture import ThreeLaneSourceRecorder
from test_three_lane_route import corridor
from test_three_lane_source_capture import Ego


class ThreeLaneFinalizerTests(unittest.TestCase):
    def fixture(self, root):
        _, route = corridor()
        recorder = ThreeLaneSourceRecorder(root, route[0], Ego(0))
        trace, video = [], []
        for index in range(3):
            frame, time_s = 51 + index, index * 0.05
            recorder.append(frame, time_s)
            trace.append({'frame': frame, 'time_s': time_s})
            video.append({'video_frame': index, 'carla_frame': frame, 'time_s': time_s})
        for name, rows in (('trace.jsonl', trace), ('video_frames.jsonl', video)):
            (root / name).write_text(''.join(json.dumps(row) + '\n' for row in rows))
        (root / 'config.json').write_text(json.dumps({
            'selected_case_id': PREFIX + 'right_baseline',
            'law_id': 'NRS-484B-223-2', 'cell_id': 'C305951',
            'actor': 'motor_vehicle_driver',
            'case': {'recording_description': {'channels': [{'name': 'three_lane_observation'}]}}}) + '\n')

    def test_saved_sources_join_and_derived_channel(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            report = analyze(root)
            self.assertEqual(report['case_id'], PREFIX + 'right_baseline')
            self.assertFalse(report['legal_acceptance_claimed'])
            result = build_result(root, report)
            self.assertEqual(result['case_id'], report['case_id'])
            self.assertEqual(len((root / 'three_lane_observation.jsonl').read_text().splitlines()), 3)
            with self.assertRaisesRegex(ValueError, 'Retain prior'):
                build_result(root, report)

    def test_missing_and_stale_original_frame_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            path = root / 'three_lane_frames.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[1]['frame'] = 900
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'join'):
                analyze(root)
            path.unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                analyze(root)

    def test_independent_saved_audit_rejects_changed_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            attempt = root / 'attempt'
            attempt.mkdir()
            self.fixture(attempt)
            report = analyze(attempt)
            result = build_result(attempt, report)
            analysis = root / 'saved' / 'analysis'
            analysis.mkdir(parents=True)
            (analysis / 'analysis-report.json').write_text(json.dumps(report) + '\n')
            (analysis / 'result.json').write_text(json.dumps(result) + '\n')
            receipt = analysis.parent / 'processing.json'
            receipt.write_text(json.dumps({'case_id': report['case_id'],
                'passed': True, 'recorded_only': True, 'originals_preserved': True,
                'missing_evidence': False, 'physical_acceptance_claimed': False,
                'legal_acceptance_claimed': False}) + '\n')
            self.assertTrue(audit(attempt, receipt)['source_binding_passed'])
            with (attempt / 'three_lane_frames.jsonl').open('a') as output:
                output.write('{}\n')
            with self.assertRaisesRegex(ValueError, 'original source differs'):
                audit(attempt, receipt)


if __name__ == '__main__':
    unittest.main()
