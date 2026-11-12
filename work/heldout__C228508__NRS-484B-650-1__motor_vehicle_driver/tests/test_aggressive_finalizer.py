from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aggressive_finalizer import ASSIGNMENT, analyze, build_result
from window_audit import audit


class FinalizerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = ASSIGNMENT + '__repeated_following'
        self.config = {
            'selected_case_id': self.case, 'law_id': 'NRS-484B-650-1',
            'cell_id': 'C228508', 'actor': 'motor_vehicle_driver',
            'case': {'recording_description': {
                'channels': [{'name': 'path_length_m', 'unit': 'm'}],
                'context_inputs': [], 'limitations': ['CPU fixture only']}}}
        self.trace = [{'frame': 100 + i, 'time_s': i * .05,
                       'x_m': i * 2.0, 'y_m': 0.0} for i in range(5)]
        self.mapping = [{'video_frame': i, 'carla_frame': row['frame'],
                         'time_s': row['time_s']} for i, row in enumerate(self.trace)]
        self.events = []

    def write(self):
        (self.root / 'config.json').write_text(json.dumps(self.config))
        (self.root / 'driving_trace.jsonl').write_text(''.join(
            json.dumps(row) + '\n' for row in self.trace))
        (self.root / 'video_frames.jsonl').write_text(''.join(
            json.dumps(row) + '\n' for row in self.mapping))
        (self.root / 'following_sources.jsonl').write_text(''.join(
            json.dumps({'frame': row['frame'], 'time_s': row['time_s'],
                        'ego_station_m': row['x_m']}) + '\n'
            for row in self.trace))
        digest = sha256((self.root / 'driving_trace.jsonl').read_bytes()).hexdigest()
        events = [{'frame': 100 + i, 'category': category,
                   'occurrence_id': str(i), 'source_ref': 'driving_trace.jsonl',
                   'source_sha256': digest,
                   **({'target_type': 'vehicle'} if category == 'hazard' else {})}
                  for i, category in enumerate(self.events)]
        (self.root / 'event_annotations.json').write_text(json.dumps(events))

    def test_saved_measurement_and_derived_channel(self):
        self.events = ['speed', 'too_close', 'too_close', 'hazard']
        self.write()
        report = analyze(self.root)
        self.assertEqual(report['case_id'], self.case)
        self.assertEqual(report['measurements']['aggressive_window_observation']
                         ['value']['candidate_window']['path_m'], 6)
        result = build_result(self.root, report)
        self.assertEqual(result['realized_observables']['path_length_m']['value'], 8)
        self.assertEqual(len((self.root / 'path_length_m.jsonl').read_text().splitlines()), 5)
        self.assertFalse(result['physical_acceptance_claimed'])
        self.assertFalse(result['legal_acceptance_claimed'])
        with self.assertRaisesRegex(ValueError, 'Retain prior'):
            build_result(self.root, report)

    def test_missing_and_misaligned_original_sources_rejected(self):
        self.events = ['speed', 'too_close', 'too_close', 'hazard']
        self.write()
        (self.root / 'event_annotations.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing required source'):
            analyze(self.root)
        self.write()
        self.mapping[2]['carla_frame'] = 999
        self.write()
        with self.assertRaisesRegex(ValueError, 'frame-map join failed'):
            analyze(self.root)
        self.mapping[2]['carla_frame'] = 102
        self.config['cell_id'] = 'wrong'
        self.write()
        with self.assertRaisesRegex(ValueError, 'Wrong exact'):
            analyze(self.root)

    def test_independent_window_audit_rejects_stale_source_and_result(self):
        self.events = ['speed', 'too_close', 'too_close', 'hazard']
        self.write()
        report_path = self.root / 'analysis.json'
        report = analyze(self.root)
        report_path.write_text(json.dumps(report))
        self.assertEqual(audit(self.root, report_path)['sources_checked'], 3)
        report['measurements']['aggressive_window_observation']['value']['candidate_window']['path_m'] = 5
        report_path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'Candidate window differs'):
            audit(self.root, report_path)
        report_path.write_text(json.dumps(analyze(self.root)))
        (self.root / 'driving_trace.jsonl').write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'Changed retained'):
            audit(self.root, report_path)


if __name__ == '__main__':
    unittest.main()
