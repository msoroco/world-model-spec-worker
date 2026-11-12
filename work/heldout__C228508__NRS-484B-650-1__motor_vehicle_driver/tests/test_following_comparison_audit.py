from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aggressive_finalizer import analyze
from following_comparison_audit import PREFIX, audit_pair, audit_speed_pair


class ComparisonAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.two, self.one = self.base / 'two', self.base / 'one'
        for root, short, count in ((self.two, 'repeated_following', 2),
                                   (self.one, 'one_secondary_act', 1)):
            root.mkdir()
            config = {'selected_case_id': PREFIX + short,
                      'law_id': 'NRS-484B-650-1', 'cell_id': 'C228508',
                      'actor': 'motor_vehicle_driver', 'rate_hz': 20,
                      'frames': 5, 'duration_s': .25, 'required_atoms': [],
                      'source_packets': [], 'cameras': ['four fixed views'],
                      'engineering': {}, 'closing_encounters': count,
                      'case': {'recording_description': {'channels': [],
                              'context_inputs': [], 'limitations': ['fixture']}}}
            (root / 'config.json').write_text(json.dumps(config))
            trace = [{'frame': 100+i, 'time_s': i*.05, 'x_m': i*2.0,
                      'y_m': 0.0} for i in range(5)]
            mapping = [{'video_frame': i, 'carla_frame': row['frame'],
                        'time_s': row['time_s']} for i, row in enumerate(trace)]
            (root / 'driving_trace.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in trace))
            (root / 'video_frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in mapping))
            (root / 'following_sources.jsonl').write_text(''.join(json.dumps({
                'frame': r['frame'], 'ego': r['x_m'], 'lead': r['x_m']+20})+'\n' for r in trace))
            source_sha = sha256((root/'following_sources.jsonl').read_bytes()).hexdigest()
            categories = ['speed', 'too_close'] + (['too_close'] if count == 2 else []) + ['hazard']
            events = []
            for i, category in enumerate(categories):
                event = {'frame': 100+i, 'category': category,
                         'occurrence_id': str(i), 'source_ref': 'following_sources.jsonl',
                         'source_sha256': source_sha}
                if category == 'hazard':
                    event['target_type'] = 'vehicle'
                events.append(event)
            (root / 'event_annotations.json').write_text(json.dumps(events))
            (root / 'analysis-report.json').write_text(json.dumps(analyze(root)))

    def test_fixed_conditions_and_declared_difference(self):
        receipt = audit_pair(self.two, self.one)
        self.assertEqual(receipt['measured_window_present'], [True, False])
        config_path = self.one / 'config.json'
        config = json.loads(config_path.read_text())
        config['duration_s'] = 1
        config_path.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, 'Fixed construction changed'):
            audit_pair(self.two, self.one)

    def test_changed_original_and_report_rejected(self):
        source = self.one / 'following_sources.jsonl'
        source.write_text(source.read_text() + '{}\n')
        with self.assertRaisesRegex(ValueError, 'Fixed original source changed'):
            audit_pair(self.two, self.one)
        self.setUp()
        report_path = self.two / 'analysis-report.json'
        report = json.loads(report_path.read_text())
        report['measurements']['aggressive_window_observation']['value']['candidate_window'] = None
        report_path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'Candidate window differs'):
            audit_pair(self.two, self.one)

    def test_speed_request_comparison_and_confounder_rejection(self):
        config_path = self.one / 'config.json'
        config = json.loads(config_path.read_text())
        config['selected_case_id'] = PREFIX + 'no_speed'
        config['closing_encounters'] = 2
        config['engineering'] = {'requested_speed_cap_mps': 13}
        config_path.write_text(json.dumps(config))
        events = json.loads((self.two / 'event_annotations.json').read_text())
        (self.one / 'event_annotations.json').write_text(json.dumps(
            [item for item in events if item['category'] != 'speed']))
        (self.one / 'analysis-report.json').write_text(json.dumps(analyze(self.one)))
        self.assertEqual(audit_speed_pair(self.two, self.one)['measured_window_present'],
                         [True, False])
        config['engineering']['route_candidate_index'] = 1
        config_path.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, 'confounded'):
            audit_speed_pair(self.two, self.one)


if __name__ == '__main__':
    unittest.main()
